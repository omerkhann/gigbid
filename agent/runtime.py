"""Running graphs for real users: shared by the worker (which executes) and the API (which reads).

- Checkpointer: AsyncPostgresSaver. Memory: PostgresStore (style and outcome memory).
- Each user's MCP sessions use that user's own bearer tokens (decrypted from `credentials`).
- Every node update is published as an event (Redis pub/sub in production) so the UI can stream
  progress; the final state is summarised into the `runs` table for the inbox.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Self

from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph, start_input
from agent.graphs.conversation_graph import build_conversation_graph, start_conversation_input
from agent.mcp_client import McpGateway, http_session_factory
from agent.nodes.common import Deps
from agent.tracing import run_attributes

ROOT = Path(__file__).resolve().parents[1]
Publish = Callable[[dict], Awaitable[None]]
MCP_URLS = {"marketplace": ("MARKETPLACE_MCP_URL", "http://127.0.0.1:8201/mcp"),
            "portfolio": ("PORTFOLIO_MCP_URL", "http://127.0.0.1:8203/mcp"),
            "workspace": ("WORKSPACE_MCP_URL", "http://127.0.0.1:8202/mcp")}


def user_profile(user: dict) -> dict:
    """The `user` dict nodes see: id, persona folder, floors."""
    s = user.get("settings") or {}
    return {"user_id": user["user_id"], "persona": user["persona"],
            "portfolio_dir": str(ROOT / "data/personas" / user["persona"]),
            "hourly_floor": s.get("hourly_floor", 25), "fixed_floor": s.get("fixed_floor", 100),
            "hourly_rate": s.get("hourly_rate")}


def gateway_for(tokens: dict[str, str]) -> McpGateway:
    return McpGateway({name: http_session_factory(os.environ.get(env, default), tokens[name])
                       for name, (env, default) in MCP_URLS.items() if name in tokens})


class Runtime:
    """`async with Runtime() as rt:` opens the Postgres checkpointer and store."""

    def __init__(self, db_url: str | None = None, gateway_factory: Callable[[dict], McpGateway] | None = None,
                 llm=None, saver=None, store=None):
        self.db_url = db_url or os.environ.get("DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5433/gigbid")
        self.gateway_factory = gateway_factory
        self.llm, self.saver, self.store = llm, saver, store
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        if self.saver is None:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            self.saver = await self._stack.enter_async_context(AsyncPostgresSaver.from_conn_string(self.db_url))
            await self.saver.setup()
        if self.store is None:
            from langgraph.store.postgres import PostgresStore
            self.store = self._stack.enter_context(PostgresStore.from_conn_string(self.db_url))
            self.store.setup()
        self.bid = build_bid_graph(self.saver)
        self.conversation = build_conversation_graph(self.saver)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def config(self, user: dict, thread_id: str, trace_id: str | None, tokens: dict[str, str]) -> dict:
        gateway = self.gateway_factory(user) if self.gateway_factory else gateway_for(tokens)
        deps = Deps(gateway=gateway, store=self.store, **({"llm": self.llm} if self.llm else {}))
        return {"configurable": {"thread_id": thread_id, "trace_id": trace_id or uuid.uuid4().hex, "deps": deps}}

    # --- running ---------------------------------------------------------------------------------

    async def _stream(self, graph, inp: Any, cfg: dict, publish: Publish) -> dict:
        thread = cfg["configurable"]["thread_id"]
        user_id = thread.split(":")[1] if thread.count(":") >= 2 else "unknown"
        t = time.time()
        with run_attributes(thread, cfg["configurable"]["trace_id"], user_id):
            async for chunk in graph.astream(inp, cfg, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        await publish({"thread_id": thread, "type": "awaiting_approval"})
                        continue
                    for e in (update or {}).get("events") or []:
                        await publish({"thread_id": thread, "type": "node", **e,
                                       "status": (update or {}).get("status")})
        snap = await graph.aget_state(cfg)
        values = dict(snap.values)
        if snap.interrupts:
            values["status"] = values.get("status") if values.get("status") != "running" else "awaiting_approval"
            values["__interrupt__"] = [i.value for i in snap.interrupts]
        values["_latency_ms"] = int((time.time() - t) * 1000)
        await publish({"thread_id": thread, "type": "finished", "status": values.get("status"),
                       "status_reason": values.get("status_reason")})
        return values

    async def run_bid(self, user: dict, job: dict, tokens: dict, publish: Publish, trace_id: str | None = None) -> dict:
        thread = f"bid:{user['user_id']}:{job['job_id']}"
        cfg = self.config(user, thread, trace_id, tokens)
        return await self._stream(self.bid, start_input(user_profile(user), job), cfg, publish)

    async def resume_bid(self, user: dict, thread: str, decision: dict, tokens: dict, publish: Publish,
                         trace_id: str | None = None) -> dict:
        cfg = self.config(user, thread, trace_id, tokens)
        return await self._stream(self.bid, Command(resume=decision), cfg, publish)

    async def run_conversation(self, user: dict, conversation_id: str, tokens: dict, publish: Publish,
                               trace_id: str | None = None) -> dict:
        thread = f"conv:{user['user_id']}:{conversation_id}"
        cfg = self.config(user, thread, trace_id, tokens)
        return await self._stream(self.conversation, start_conversation_input(user_profile(user), conversation_id),
                                  cfg, publish)

    async def resume_conversation(self, user: dict, thread: str, decision: dict, tokens: dict, publish: Publish,
                                  trace_id: str | None = None) -> dict:
        cfg = self.config(user, thread, trace_id, tokens)
        return await self._stream(self.conversation, Command(resume=decision), cfg, publish)

    async def state(self, kind: str, thread: str) -> dict:
        graph = self.bid if kind == "bid" else self.conversation
        snap = await graph.aget_state({"configurable": {"thread_id": thread}})
        values = dict(snap.values)
        if snap.interrupts:
            values["__interrupt__"] = [i.value for i in snap.interrupts]
        return values


def run_summary(kind: str, values: dict) -> dict:
    """What the inbox needs, without loading the whole checkpoint."""
    if kind == "bid":
        return {"category": (values.get("job") or {}).get("category"), "fit": (values.get("fit_report") or {}).get("score"), "risk": (values.get("risk_report") or {}).get("score"),
                "risk_flags": (values.get("risk_report") or {}).get("flags", []),
                "decision": (values.get("decision") or {}).get("action"),
                "price": (values.get("price_quote") or {}).get("amount"),
                "unit": (values.get("price_quote") or {}).get("unit"),
                "connects": (values.get("price_quote") or {}).get("connects_cost")}
    return {"intent": (values.get("intent") or {}).get("intent"), "flags": (values.get("intent") or {}).get("flags", [])}


def dumps(o: Any) -> str:
    return json.dumps(o, default=str)
