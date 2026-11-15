"""Workspace MCP server with a fixed clock: Monday 2026-11-16 08:00 in Asia/Karachi (03:00 UTC)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.workspace.server import Settings, build_server

NOW = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


@pytest.fixture
def server(tmp_path):
    return build_server(Settings(db_path=tmp_path / "ws.sqlite3", now=lambda: NOW))


def ok(r) -> dict:
    assert not r.isError, r.content[0].text
    return r.structuredContent


def err(r) -> dict:
    assert r.isError
    t = r.content[0].text
    return json.loads(t[t.index("{"):])


def key() -> str:
    return uuid.uuid4().hex


async def test_free_slots_respect_notice_meetings_and_hours(server):
    async with connect(server) as s:
        out = ok(await s.call_tool("get_free_slots", {"days": 3, "max_slots": 6,
                                                      "client_timezone": "America/New_York"}))
    starts = [x["start_local"] for x in out["slots"]]
    # 08:00 now + 2h notice = 10:00, but 10:00-10:30 is standup -> first slot 10:30, then a gap.
    assert starts[0] == "2026-11-16T10:30:00+05:00"
    assert starts[1] == "2026-11-16T11:30:00+05:00"
    assert starts[2].startswith("2026-11-17T09:00")  # at most two per day
    assert out["slots"][0]["start_client"] == "2026-11-16T00:30:00-05:00"
    assert len(out["slots"]) == 6


async def test_hold_blocks_slot_and_release_frees_it(server):
    async with connect(server) as s:
        k = key()
        hold = ok(await s.call_tool("create_interview_hold", {"start": "2026-11-16T10:30:00+05:00",
                                                              "ref": "thr-abc123", "idempotency_key": k}))
        again = ok(await s.call_tool("create_interview_hold", {"start": "2026-11-16T10:30:00+05:00",
                                                               "ref": "thr-abc123", "idempotency_key": k}))
        assert again == hold and hold["status"] == "tentative"
        slots = ok(await s.call_tool("get_free_slots", {"days": 1}))["slots"]
        assert all(x["start_local"] != "2026-11-16T10:30:00+05:00" for x in slots)
        clash = err(await s.call_tool("create_interview_hold", {"start": "2026-11-16T10:45:00+05:00",
                                                                "ref": "thr-x", "idempotency_key": key()}))
        assert clash["error"] == "slot_unavailable"
        ok(await s.call_tool("release_hold", {"hold_id": hold["hold_id"], "idempotency_key": key()}))
        assert ok(await s.call_tool("list_holds", {}))["holds"] == []


@pytest.mark.parametrize(("start", "reason"), [
    ("2026-11-16T09:00:00+05:00", "less than 2 hours"),
    ("2026-11-16T10:00:00+05:00", "overlaps"),            # standup
    ("2026-11-16T18:00:00+05:00", "outside working hours"),
    ("2026-11-21T11:00:00+05:00", "outside working days"),  # Saturday
])
async def test_bad_hold_times_are_refused(server, start, reason):
    async with connect(server) as s:
        e = err(await s.call_tool("create_interview_hold", {"start": start, "ref": "thr-1", "idempotency_key": key()}))
    assert e["error"] == "slot_unavailable" and reason in e["detail"]


async def test_email_drafts_are_saved_not_sent_and_audit_is_masked(server):
    async with connect(server) as s:
        d = ok(await s.call_tool("create_email_draft", {"to": "client@example.com", "subject": "Interview",
                                                        "body": "Call me on +92 300 1234567.", "idempotency_key": key()}))
        drafts = ok(await s.call_tool("list_email_drafts", {}))["drafts"]
    assert d["status"] == "draft" and drafts[0]["draft_id"] == d["draft_id"]
    row = next(r for r in server.state["audit"].audit_rows() if r["tool"] == "create_email_draft")
    assert "[EMAIL]" in row["args"] and "[PHONE]" in row["args"] and "1234567" not in row["args"]


async def test_invalid_timezone_and_datetime(server):
    async with connect(server) as s:
        assert err(await s.call_tool("get_free_slots", {"client_timezone": "Mars/Base"}))["error"] == "invalid_timezone"
        e = err(await s.call_tool("create_interview_hold", {"start": "2026-11-16T10:30:00", "ref": "thr-1",
                                                            "idempotency_key": key()}))
        assert e["error"] == "invalid_datetime"
