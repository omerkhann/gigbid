"""API + worker tasks end to end: real Postgres (gigbid_test database), inline task queue, in-process
GigSim and MCP servers, fake LLM, in-memory checkpointer. Skipped if Postgres isn't reachable."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import psycopg
import pytest
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
from rag.retriever import reset_cache
from tests.integration.test_bid_graph import FakeLLM
from worker.queue import InlineQueue, MemoryEvents

ROOT = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5433/gigbid")
TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5433/gigbid_test")
JOB = "job-0b954e1ba14e"   # a data-analyst "bid" job in the dev pack


def _postgres_ready() -> bool:
    try:
        with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as c:
            if not c.execute("SELECT 1 FROM pg_database WHERE datname = 'gigbid_test'").fetchone():
                c.execute("CREATE DATABASE gigbid_test")
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _postgres_ready(), reason="Postgres not reachable")


@pytest.fixture
async def api(tmp_path):
    reset_cache()
    sim = create_gigsim({"db_path": str(tmp_path / "g.sqlite3"), "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                         "rate_limit": {"requests_per_minute": 100000, "submits_per_minute": 100000}})
    sim_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
    await sim_http.post("/admin/release_all", json={"on": True}, headers={"Authorization": "Bearer dev-admin"})
    servers = {
        "marketplace": build_marketplace(MSettings(db_path=tmp_path / "m.sqlite3", local_user="u-data-analyst",
                                                   limits={"read": 10000, "submit": 10000, "write": 10000}),
                                         GigSimBackend("http://gigsim", client=sim_http, backoff=0.01, max_wait=0.05)),
        "portfolio": build_portfolio(PSettings(embedder="hash", db_path=tmp_path / "p.sqlite3", cache_root=tmp_path / "c",
                                               local_user="u-data-analyst")),
        "workspace": build_workspace(WSettings(db_path=tmp_path / "w.sqlite3", local_user="u-data-analyst")),
    }

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    db = await Db(TEST_URL).open()
    await db.run("TRUNCATE users, sessions, credentials, saved_searches, seen_jobs, runs CASCADE")
    runtime = await Runtime(saver=InMemorySaver(), store=InMemoryStore(), llm=FakeLLM(),
                            gateway_factory=lambda user: McpGateway({k: factory(v) for k, v in servers.items()})).__aenter__()
    queue, events = InlineQueue(), MemoryEvents()
    queue.ctx.update(db=db, runtime=runtime, queue=queue, events=events)
    svc = Services(db=db, runtime=runtime, queue=queue, events=events)
    await seed(svc)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(svc)), base_url="http://api")
    yield {"client": client, "svc": svc, "sim_http": sim_http, "events": events, "queue": queue}
    await db.close()


async def login(c, email="reviewer@gigbid.dev"):
    r = await c.post("/auth/login", json={"email": email, "password": "gigbid-review"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.headers['x-session-token']}"}


async def test_login(api):
    c = api["client"]
    assert (await c.post("/auth/login", json={"email": "reviewer@gigbid.dev", "password": "wrong-pass"})).status_code == 401
    h = await login(c)
    me = (await c.get("/auth/me", headers=h)).json()
    assert me["persona"] == "data_analyst"
    c.cookies.clear()                                                    # the client kept the login cookie
    assert (await c.get("/jobs/inbox")).status_code == 401


async def test_analyze_approve_submit_and_pipeline(api):
    c, h = api["client"], await login(api["client"])
    r = await c.post(f"/jobs/{JOB}/analyze", headers={**h, "X-Trace-Id": "trace-abc"})
    assert r.status_code == 202 and r.json()["trace_id"] == "trace-abc"
    inbox = (await c.get("/jobs/inbox", headers=h)).json()
    assert inbox[0]["status"] == "awaiting_approval" and inbox[0]["summary"]["fit"] is not None
    assert inbox[0]["trace_id"] == "trace-abc"                      # one trace id from request to run
    detail = (await c.get(f"/jobs/{JOB}", headers=h)).json()
    assert detail["pending_approval"]["kind"] == "proposal_approval" and "user" not in detail["state"]
    assert [a["thread_id"] for a in (await c.get("/approvals", headers=h)).json()] == [detail["thread_id"]]
    assert any(e["type"] == "node" for e in api["events"].history["u-reviewer"])     # streamed progress
    regen = await c.post(f"/approvals/{detail['thread_id']}/regenerate",
                         json={"paragraph": "Old paragraph.", "instruction": "shorter"}, headers=h)
    assert regen.status_code == 200 and regen.json()["text"]
    r = await c.post(f"/approvals/{detail['thread_id']}", json={"action": "approve"}, headers=h)
    assert r.status_code == 202
    assert (await c.get(f"/jobs/{JOB}", headers=h)).json()["status"] == "submitted"
    again = await c.post(f"/approvals/{detail['thread_id']}", json={"action": "approve"}, headers=h)
    assert again.status_code == 409                                  # nothing left to approve
    board = (await c.get("/pipeline", headers=h)).json()["board"]
    assert any(p["job_id"] == JOB for col in ("submitted", "viewed", "replied", "interview", "lost") for p in board[col])
    stats = (await c.get("/analytics", headers=h)).json()
    assert stats["proposals_submitted"] == 1 and stats["connects_spent"] > 0


async def test_users_cannot_see_each_others_runs(api):
    c = api["client"]
    h1, h2 = await login(c), await login(c, "ml_engineer@gigbid.dev")
    await c.post(f"/jobs/{JOB}/analyze", headers=h1)
    assert (await c.get(f"/runs/bid:u-reviewer:{JOB}", headers=h2)).status_code == 404
    assert (await c.get("/jobs/inbox", headers=h2)).json() == []


async def test_scout_queues_new_jobs_once(api):
    c, h = api["client"], await login(api["client"])
    first = [d for d in api["queue"].done if d[0] == "scout"]
    assert first == []
    await c.post("/scout/run", headers=h)
    scout1 = [d for d in api["queue"].done if d[0] == "scout"][-1][2]
    assert 0 < len(scout1["queued"]) <= 5
    await c.post("/scout/run", headers=h)
    scout2 = [d for d in api["queue"].done if d[0] == "scout"][-1][2]
    assert not set(scout2["queued"]) & set(scout1["queued"])          # never re-analyses a seen job


async def test_edit_feeds_memory_viewer_and_delete(api):
    c, h = api["client"], await login(api["client"])
    await c.post(f"/jobs/{JOB}/analyze", headers=h)
    thread = f"bid:u-reviewer:{JOB}"
    edited = "I am excited about this. I built a Power BI sales dashboard and would start by agreeing your metrics."
    await c.post(f"/approvals/{thread}", json={"action": "edit", "cover_letter": edited.replace("I am excited about this. ", "")},
                 headers=h)
    mem = (await c.get("/memory", headers=h)).json()
    assert mem["style_candidates"]                                     # the edit was observed
    key = mem["style_candidates"][0]["key"]
    assert (await c.delete(f"/memory/style_candidates/{key}", headers=h)).status_code == 204


async def test_marketplace_health_reports_degraded_mode(api):
    c, h = api["client"], await login(api["client"])
    assert (await c.get("/health/marketplace", headers=h)).json()["marketplace"] == "ok"
    await api["sim_http"].post("/admin/faults", json={"down": True}, headers={"Authorization": "Bearer dev-admin"})
    assert (await c.get("/health/marketplace", headers=h)).json()["marketplace"] == "unavailable"
