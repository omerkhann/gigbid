"""Deterministic backend for the web UI's end-to-end tests (Playwright). NOT for production.

python -m apps.api.e2e_server --port 8000

The real API (same routers, auth, Postgres tables), but wired to in-process GigSim and MCP servers,
a scripted LLM (no Groq or Ollama), an inline task queue (no Redis/worker) and in-memory LangGraph
checkpoints. A fresh `gigbid_e2e` database is created on every start, so tests are repeatable.
Extra route for tests: POST /e2e/marketplace {"down": true|false}.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import psycopg
import uvicorn
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.mcp_client import McpGateway
from agent.runtime import Runtime
from apps.api.db import Db
from apps.api.main import Services, create_app, seed
from gigsim.app import create_app as create_gigsim
from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
from mcp_servers.marketplace.server import Settings as MSettings
from mcp_servers.marketplace.server import build_server as build_marketplace
from mcp_servers.portfolio.server import Settings as PSettings
from mcp_servers.portfolio.server import build_server as build_portfolio
from mcp_servers.workspace.server import Settings as WSettings
from mcp_servers.workspace.server import build_server as build_workspace
from tests.integration.test_bid_graph import FakeLLM
from worker.queue import InlineQueue, MemoryEvents

ADMIN_URL = os.environ.get("E2E_ADMIN_DATABASE_URL", "postgresql://gigbid:gigbid@127.0.0.1:5433/gigbid")
E2E_URL = ADMIN_URL.rsplit("/", 1)[0] + "/gigbid_e2e"
ADMIN = {"Authorization": "Bearer dev-admin"}


def fresh_database() -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS gigbid_e2e WITH (FORCE)")
        c.execute("CREATE DATABASE gigbid_e2e")


async def build() -> FastAPI:
    tmp = Path(tempfile.mkdtemp(prefix="gigbid-e2e-"))
    sim = create_gigsim({"db_path": str(tmp / "g.sqlite3"), "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                         "rate_limit": {"requests_per_minute": 100000, "submits_per_minute": 100000}})
    sim_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
    await sim_http.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    servers = {
        "marketplace": build_marketplace(MSettings(db_path=tmp / "m.sqlite3", local_user="u-data-analyst",
                                                   limits={"read": 100000, "submit": 100000, "write": 100000}),
                                         GigSimBackend("http://gigsim", client=sim_http, retries=1, backoff=0.01, max_wait=0.05)),
        "portfolio": build_portfolio(PSettings(embedder="hash", db_path=tmp / "p.sqlite3", cache_root=tmp / "c",
                                               local_user="u-data-analyst")),
        "workspace": build_workspace(WSettings(db_path=tmp / "w.sqlite3", local_user="u-data-analyst")),
    }

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    db = await Db(E2E_URL).open()
    runtime = await Runtime(saver=InMemorySaver(), store=InMemoryStore(), llm=FakeLLM(),
                            gateway_factory=lambda user: McpGateway({k: factory(v) for k, v in servers.items()})).__aenter__()
    queue, events = InlineQueue(), MemoryEvents()
    queue.ctx.update(db=db, runtime=runtime, queue=queue, events=events)
    svc = Services(db=db, runtime=runtime, queue=queue, events=events)
    await seed(svc)
    app = create_app(svc)

    @app.post("/e2e/marketplace", tags=["e2e"])
    async def set_marketplace(body: dict):
        await sim_http.post("/admin/faults", json={"down": bool(body.get("down"))}, headers=ADMIN)
        return {"down": bool(body.get("down"))}

    return app


async def serve(port: int) -> None:
    fresh_database()
    app = await build()
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")).serve()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    if sys.platform == "win32":
        asyncio.run(serve(a.port), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(serve(a.port))
