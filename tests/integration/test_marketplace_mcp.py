"""Marketplace MCP server end to end: in-memory MCP client -> our server -> GigSim adapter -> GigSim
(running in-process over an ASGI transport). No network, no API keys."""

from __future__ import annotations

import json
import sqlite3
import uuid

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from gigsim.app import create_app
from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
from mcp_servers.marketplace.server import Settings, build_server

ADMIN = {"Authorization": "Bearer dev-admin"}


@pytest.fixture
def world(tmp_path):
    def make(faults=None):
        sim = create_app({"db_path": str(tmp_path / "gigsim.sqlite3"),
                          "faults": faults or {"error_rate": 0.0, "latency_ms": [0, 0], "seed": 1}})
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
        backend = GigSimBackend("http://gigsim", client=http, retries=3, backoff=0.01, max_wait=0.05)
        server = build_server(Settings(db_path=tmp_path / "mcp.sqlite3", local_user="u-data-analyst"), backend)
        return sim, http, server
    return make


async def admin(http, path, body):
    r = await http.post(path, json=body, headers=ADMIN)
    assert r.status_code == 200, r.text


async def call(session, tool, trace=None, **args):
    return await session.call_tool(tool, args, meta={"trace_id": trace} if trace else None)


def ok(result) -> dict:
    assert not result.isError, result.content[0].text
    return result.structuredContent


def err(result) -> dict:
    """FastMCP reports errors as 'Error executing tool <name>: {json}'; the JSON is our error body."""
    assert result.isError
    text = result.content[0].text
    return json.loads(text[text.index("{"):])


def letter(job: dict) -> str:
    return (f"{job['title']}: I built a Power BI sales dashboard used by 40 area managers that cut "
            "monthly reporting from 3 days to 2 hours, and I would start with your key metrics.")


async def first_job(session) -> dict:
    page = ok(await call(session, "search_jobs", category="data_science", limit=5))
    return ok(await call(session, "get_job", job_id=page["jobs"][0]["job_id"]))


async def test_tools_declare_schemas_and_annotations(world):
    _, _, server = world()
    async with connect(server) as s:
        tools = {t.name: t for t in (await s.list_tools()).tools}
    assert len(tools) == 11
    for t in tools.values():
        assert t.outputSchema, t.name
    for name in ("create_proposal_draft", "submit_proposal", "send_message"):
        assert "idempotency_key" in tools[name].inputSchema["required"]
        assert tools[name].annotations.readOnlyHint is False
    assert tools["submit_proposal"].annotations.destructiveHint is True
    assert tools["search_jobs"].annotations.readOnlyHint is True


async def test_read_flow_and_private_fields(world):
    _, http, server = world()
    await admin(http, "/admin/release_all", {"on": True})
    async with connect(server) as s:
        job = await first_job(s)
        client = ok(await call(s, "get_client_history", client_id=job["client_id"]))
        stats = ok(await call(s, "get_market_stats", category="data_science"))
        bal = ok(await call(s, "get_connects_balance"))
    assert "source" not in job and "release_offset_h" not in job
    assert client["client_id"] == job["client_id"] and "message_attack" not in client
    assert stats["hourly_rate"]["p50"] > 0 and bal["balance"] == 80


async def test_submit_dry_run_then_exactly_once(world):
    _, http, server = world()
    await admin(http, "/admin/release_all", {"on": True})
    async with connect(server) as s:
        job = await first_job(s)
        draft = ok(await call(s, "create_proposal_draft", job_id=job["job_id"], cover_letter=letter(job),
                              bid_amount=30, idempotency_key=uuid.uuid4().hex))
        preview = ok(await call(s, "submit_proposal", proposal_id=draft["proposal_id"],
                                idempotency_key=uuid.uuid4().hex, dry_run=True))
        assert preview["sent"] is False and preview["balance_after"] == 80 - preview["connects_cost"]
        assert ok(await call(s, "get_connects_balance"))["balance"] == 80  # dry run spent nothing
        key = uuid.uuid4().hex
        first = ok(await call(s, "submit_proposal", proposal_id=draft["proposal_id"], idempotency_key=key))
        again = ok(await call(s, "submit_proposal", proposal_id=draft["proposal_id"], idempotency_key=key))
        assert first == again and first["sent"] is True
        assert ok(await call(s, "get_connects_balance"))["balance"] == 80 - first["connects_cost"]
        reused = err(await call(s, "submit_proposal", proposal_id="prop-other", idempotency_key=key))
        assert reused["error"] == "idempotency_key_reused"


async def test_lost_responses_are_retried_without_double_charging(world):
    sim, http, server = world({"error_rate": 0.5, "latency_ms": [0, 0], "seed": 11})
    await admin(http, "/admin/release_all", {"on": True})
    async with connect(server) as s:
        job = None
        for _ in range(10):  # reads may also exhaust retries at 50% errors
            r = await call(s, "search_jobs", category="data_science", limit=3)
            if not r.isError:
                job = r.structuredContent["jobs"][0]
                break
        assert job
        dkey, skey = uuid.uuid4().hex, uuid.uuid4().hex
        for _ in range(10):
            r = await call(s, "create_proposal_draft", job_id=job["job_id"], cover_letter=letter(job),
                           bid_amount=30, idempotency_key=dkey)
            if not r.isError:
                break
        pid = r.structuredContent["proposal_id"]
        for _ in range(10):
            r = await call(s, "submit_proposal", proposal_id=pid, idempotency_key=skey)
            if not r.isError:
                break
        assert not r.isError
    charges = sim.state.engine.store.q("SELECT * FROM ledger WHERE reason='submit' AND ref=?", (pid,))
    assert len(charges) == 1


async def test_marketplace_down_gives_a_clear_error(world):
    _, http, server = world()
    await admin(http, "/admin/faults", {"down": True})
    async with connect(server) as s:
        e = err(await call(s, "search_jobs"))
    assert e["error"] == "marketplace_unavailable"


async def test_policy_violation_is_surfaced(world):
    _, http, server = world()
    await admin(http, "/admin/release_all", {"on": True})
    async with connect(server) as s:
        job = await first_job(s)
        draft = ok(await call(s, "create_proposal_draft", job_id=job["job_id"],
                              cover_letter=letter(job) + " Reach me at me@example.com.",
                              bid_amount=30, idempotency_key=uuid.uuid4().hex))
        preview = ok(await call(s, "submit_proposal", proposal_id=draft["proposal_id"],
                                idempotency_key=uuid.uuid4().hex, dry_run=True))
        assert preview["policy_violations"][0]["rule_id"] == "no_contact_details"
        e = err(await call(s, "submit_proposal", proposal_id=draft["proposal_id"], idempotency_key=uuid.uuid4().hex))
    assert e["error"] == "policy_violation" and e["violations"][0]["rule_id"] == "no_contact_details"


async def test_input_constraints_reject_bad_calls(world):
    _, _, server = world()
    async with connect(server) as s:
        r = await call(s, "create_proposal_draft", job_id="job-x1", cover_letter="too short",
                       bid_amount=30, idempotency_key=uuid.uuid4().hex)
        assert r.isError
        r = await call(s, "create_proposal_draft", job_id="job-x1", cover_letter="x" * 60,
                       bid_amount=-5, idempotency_key=uuid.uuid4().hex)
        assert r.isError


async def test_audit_log_is_append_only_masked_and_traced(world, tmp_path):
    _, http, server = world()
    await admin(http, "/admin/release_all", {"on": True})
    async with connect(server) as s:
        job = await first_job(s)
        await call(s, "create_proposal_draft", trace="trace-123", job_id=job["job_id"],
                   cover_letter=letter(job) + " Call +1 (555) 123-4567.", bid_amount=30,
                   idempotency_key=uuid.uuid4().hex)
    rows = server.state["store"].audit_rows()
    draft_row = next(r for r in rows if r["tool"] == "create_proposal_draft")
    assert draft_row["trace_id"] == "trace-123" and draft_row["user_id"] == "u-data-analyst"
    assert "[PHONE]" in draft_row["args"] and "555" not in draft_row["args"]
    conn = sqlite3.connect(tmp_path / "mcp.sqlite3")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE audit SET status = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM audit")


async def test_message_dry_run_and_send(world):
    sim, http, server = world()
    await admin(http, "/admin/release_all", {"on": True})
    engine = sim.state.engine
    # Find a job the heuristic client will answer: a strong letter naming the must-haves.
    async with connect(server) as s:
        page = ok(await call(s, "search_jobs", category="data_science", limit=40))
        thread_id = None
        for j in page["jobs"]:
            must = [m["skill"] for m in engine.world.hidden[j["job_id"]]["must_have"]]
            full = ok(await call(s, "get_job", job_id=j["job_id"]))
            text = (f"{full['title']}: I used {', '.join(must)} on a dashboard that cut reporting time by 80% "
                    "for 40 managers, and I can start this week.")
            d = ok(await call(s, "create_proposal_draft", job_id=j["job_id"], cover_letter=text,
                              bid_amount=(full["budget_max"] or 30) * 0.9,
                              screening_answers=["Yes, a Power BI project."] * len(full["screening_questions"]),
                              idempotency_key=uuid.uuid4().hex))
            sub = ok(await call(s, "submit_proposal", proposal_id=d["proposal_id"], idempotency_key=uuid.uuid4().hex))
            if sub["status"] in ("replied", "interview"):
                thread_id = ok(await call(s, "list_threads"))["threads"][0]["thread_id"]
                break
        assert thread_id, "no client replied in the first 40 jobs"
        bad = ok(await call(s, "send_message", thread_id=thread_id, body="Email me at a@b.co",
                            idempotency_key=uuid.uuid4().hex, dry_run=True))
        assert bad["policy_violations"][0]["rule_id"] == "no_contact_details" and bad["sent"] is False
        sent = ok(await call(s, "send_message", thread_id=thread_id, body="Happy to talk Tuesday 3pm UTC.",
                             idempotency_key=uuid.uuid4().hex))
        assert sent["sent"] and sent["thread"]["messages"][-1]["sender"] == "client"
