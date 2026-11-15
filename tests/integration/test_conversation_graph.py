"""Conversation graph end to end, in-process: GigSim + Marketplace and Workspace MCP servers, a fake
LLM, an in-memory checkpointer and memory store. Conversations are created in GigSim by submitting
strong proposals until clients reply."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.graphs.conversation_graph import build_conversation_graph, start_conversation_input
from agent.handoffs import IntentLLM, ReplyLLM
from agent.llm import Usage
from agent.mcp_client import McpGateway
from agent.memory.store import style_rules
from agent.nodes.common import Deps
from gigsim.app import create_app
from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
from mcp_servers.marketplace.server import Settings as MSettings
from mcp_servers.marketplace.server import build_server as build_marketplace
from mcp_servers.workspace.server import Settings as WSettings
from mcp_servers.workspace.server import build_server as build_workspace

ROOT = Path(__file__).resolve().parents[2]
ADMIN = {"Authorization": "Bearer dev-admin"}
ANALYST = {"Authorization": "Bearer dev-data-analyst"}
USER = {"user_id": "u-data-analyst", "persona": "data_analyst", "portfolio_dir": str(ROOT / "data/personas/data_analyst")}


class FakeLLM:
    def __init__(self, reply="Thanks for your message! Happy to explain my approach here on the platform."):
        self.reply, self.systems = reply, []

    def __call__(self, node, schema):
        def call(messages):
            text = "\n".join(m.content for m in messages)
            if node == "intent":
                newest = text.split("Newest client message(s):", 1)[1].lower()
                call_words = any(w in newest for w in ("call", "schedule", "interview", "times"))
                out = IntentLLM(intent="interview_request" if call_words else "question", wants_call=call_words,
                                summary="client message")
            else:
                self.systems.append(messages[0].content)
                out = ReplyLLM(reply=self.reply)
            return out, Usage("fake", 10, 10, 0.0, 0)
        return call


@pytest.fixture
async def env(tmp_path):
    # High rate limits: the setup submits 40 proposals in a burst to create conversations.
    sim = create_app({"db_path": str(tmp_path / "g.sqlite3"), "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                      "rate_limit": {"requests_per_minute": 100000, "submits_per_minute": 100000}})
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
    await http.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    market = build_marketplace(MSettings(db_path=tmp_path / "m.sqlite3", local_user="u-data-analyst"),
                               GigSimBackend("http://gigsim", client=http, backoff=0.01, max_wait=0.05))
    # Monday 08:00 Karachi: free slots exist later that day.
    workspace = build_workspace(WSettings(db_path=tmp_path / "w.sqlite3", local_user="u-data-analyst",
                                          now=lambda: datetime(2026, 11, 16, 3, 0, tzinfo=UTC)))

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    return {"sim": sim, "http": http, "workspace": workspace,
            "gateway": McpGateway({"marketplace": factory(market), "workspace": factory(workspace)})}


async def make_threads(env, n=40) -> list[dict]:
    """Submit strong proposals (naming the client's must-haves) until clients reply; return threads."""
    engine = env["sim"].state.engine
    labels = [json.loads(line) for line in (ROOT / "evals/datasets/dev/labels.jsonl").open(encoding="utf-8")]
    for lab in [r for r in labels if r["persona"] == "data_analyst" and r["bid"]][:n]:
        job = engine.world.jobs[lab["job_id"]]
        must = [m["skill"] for m in engine.world.hidden[job["job_id"]]["must_have"]]
        letter = f"{job['title']}: I used {', '.join(must)} on a dashboard that cut reporting time by 80% for 40 managers."
        r = await env["http"].post("/proposals", headers={**ANALYST, "Idempotency-Key": uuid.uuid4().hex}, json={
            "job_id": job["job_id"], "cover_letter": letter, "bid_amount": (job["budget_max"] or 30) * 0.9,
            "screening_answers": ["Yes, a Power BI project."] * len(job["screening_questions"])})
        await env["http"].post(f"/proposals/{r.json()['proposal_id']}/submit",
                               headers={**ANALYST, "Idempotency-Key": uuid.uuid4().hex})
    return (await env["http"].get("/threads", headers=ANALYST)).json()["threads"]


def cfg(env, llm, thread, store=None):
    return {"configurable": {"thread_id": thread, "deps": Deps(gateway=env["gateway"], llm=llm, store=store)}}


def client_of(env, thread):
    return env["sim"].state.engine.world.clients[thread["client_id"]]


async def test_question_reply_is_approved_and_sent(env):
    threads = await make_threads(env)
    t = next(t for t in threads if not client_of(env, t)["message_attack"])
    graph = build_conversation_graph(InMemorySaver())
    c = cfg(env, FakeLLM(), "conv-1")
    out = await graph.ainvoke(start_conversation_input(USER, t["thread_id"]), c)
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "message_approval" and payload["draft"]["body"].startswith("Thanks")
    done = await graph.ainvoke(Command(resume={"action": "approve"}), c)
    assert done["status"] == "sent"
    msgs = (await env["http"].get(f"/threads/{t['thread_id']}", headers=ANALYST)).json()["messages"]
    assert [m["sender"] for m in msgs][-2:] == ["freelancer", "client"]       # sent, and the client answered
    again = await graph.ainvoke(start_conversation_input(USER, t["thread_id"]), c)
    assert again["status"] in ("no_action", "running") or "__interrupt__" in again   # new run on same thread works


async def test_interview_request_offers_real_slots_and_places_holds(env):
    threads = await make_threads(env)
    t = next(t for t in threads if t["status"] == "interview" and not client_of(env, t)["message_attack"])
    graph = build_conversation_graph(InMemorySaver())
    c = cfg(env, FakeLLM(reply="Great - I can do any of the times below; which suits you?"), "conv-2")
    out = await graph.ainvoke(start_conversation_input(USER, t["thread_id"]), c)
    draft = out["__interrupt__"][0].value["draft"]
    assert draft["intent"] == "interview_request" and len(draft["offered_slots"]) == 3
    done = await graph.ainvoke(Command(resume={"action": "approve"}), c)
    assert done["status"] == "sent" and len(done["holds"]) == 3
    assert all(h["status"] == "tentative" for h in done["holds"])


async def test_off_platform_request_is_flagged_as_scam_signal(env):
    threads = await make_threads(env)
    t = next((t for t in threads if (client_of(env, t)["message_attack"] or {}).get("type") == "off_platform"), None)
    if t is None:
        pytest.skip("no off-platform client replied in this sample")
    out = await build_conversation_graph(InMemorySaver()).ainvoke(
        start_conversation_input(USER, t["thread_id"]), cfg(env, FakeLLM(), "conv-3"))
    intent = out["__interrupt__"][0].value["intent"]
    assert intent["intent"] == "scam_signal" and "scam_signal" in intent["flags"]
    assert out["__interrupt__"][0].value["draft"]["offered_slots"] == []      # no call slots for a scam signal


async def test_reply_with_contact_details_is_fixed_by_compliance(env):
    t = next(t for t in await make_threads(env) if not client_of(env, t)["message_attack"])
    llm = FakeLLM(reply="Thanks for asking! Email me at me@example.com for details. I can start on Monday.")
    out = await build_conversation_graph(InMemorySaver()).ainvoke(
        start_conversation_input(USER, t["thread_id"]), cfg(env, llm, "conv-4"))
    body = out["__interrupt__"][0].value["draft"]["body"]
    assert "example.com" not in body and "Monday" in body


async def test_edits_teach_style_memory(env):
    threads = [t for t in await make_threads(env) if not client_of(env, t)["message_attack"]]
    store = InMemoryStore()
    original = "I am a passionate analyst. Thanks for your message, happy to explain my approach here."
    edited = "Thanks for your message, happy to explain my approach here."
    for i, t in enumerate(threads[:3]):
        graph = build_conversation_graph(InMemorySaver())
        c = cfg(env, FakeLLM(reply=original), f"style-{i}", store)
        await graph.ainvoke(start_conversation_input(USER, t["thread_id"]), c)
        out = await graph.ainvoke(Command(resume={"action": "edit", "cover_letter": edited}), c)
        assert "__interrupt__" in out                                  # edited draft re-checked, asks again
        await graph.ainvoke(Command(resume={"action": "approve"}), c)
    rules = style_rules(store, "u-data-analyst")
    assert any("passionate" in r for r in rules)
    llm = FakeLLM()                                                    # the next draft is told the rule
    await build_conversation_graph(InMemorySaver()).ainvoke(
        start_conversation_input(USER, threads[3]["thread_id"]), cfg(env, llm, "style-next", store))
    assert "passionate" in llm.systems[-1]
