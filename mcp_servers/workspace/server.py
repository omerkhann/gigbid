"""Workspace MCP server (assignment A3): calendar slots, tentative interview holds, email drafts.

A local mock, as the assignment allows: each user has working hours and a few recurring busy
blocks; holds and drafts live in SQLite. Nothing is ever sent - email drafts stay drafts.

Run (Streamable HTTP, bearer auth):  python -m mcp_servers.workspace.server
Settings (environment): WORKSPACE_USERS (JSON), WORKSPACE_LOCAL_USER, WORKSPACE_DB,
WORKSPACE_HOST / WORKSPACE_PORT (default 127.0.0.1:8202).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from mcp_servers.common.auth import StaticTokenVerifier, auth_settings
from mcp_servers.common.guard import GuardStore, RateLimiter, ToolFailure, ToolGuard

ROOT = Path(__file__).resolve().parents[2]
SLOT_STEP = timedelta(minutes=30)
MIN_NOTICE = timedelta(hours=2)

# Recurring busy blocks: (weekday 0=Mon, start "HH:MM", end "HH:MM", title), in the user's timezone.
DEFAULT_BUSY = [(d, "10:00", "10:30", "Daily standup") for d in range(5)] + [
    (2, "14:00", "16:00", "Client work block"), (4, "16:00", "17:00", "Weekly review")]

DEV_USERS = [
    {"token": f"dev-ws-{p}", "user_id": f"u-{p}", "timezone": "Asia/Karachi", "work_hours": ["09:00", "17:00"],
     "workdays": [0, 1, 2, 3, 4], "busy": DEFAULT_BUSY}
    for p in ("ml-engineer", "fullstack-dev", "data-analyst")
]


@dataclass
class Settings:
    users: list[dict] = field(default_factory=lambda: [dict(u) for u in DEV_USERS])
    local_user: str | None = None
    db_path: Path = ROOT / "data/processed/workspace_mcp.sqlite3"
    host: str = "127.0.0.1"
    port: int = 8202
    limits: dict[str, int] = field(default_factory=lambda: {"read": 60, "write": 30})
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    @classmethod
    def from_env(cls) -> Settings:
        s = cls()
        if "WORKSPACE_USERS" in os.environ:
            s.users = json.loads(os.environ["WORKSPACE_USERS"])
        s.local_user = os.environ.get("WORKSPACE_LOCAL_USER", s.local_user)
        if "WORKSPACE_DB" in os.environ:
            s.db_path = Path(os.environ["WORKSPACE_DB"])
        s.host = os.environ.get("WORKSPACE_HOST", s.host)
        s.port = int(os.environ.get("WORKSPACE_PORT", s.port))
        return s


# --- schemas ---------------------------------------------------------------------------------

Iso = Field(description="ISO 8601 datetime with timezone, e.g. 2026-11-17T10:30:00+05:00")


class Slot(BaseModel):
    start_utc: str
    end_utc: str
    start_local: str = Field(description="Start in the freelancer's timezone")
    start_client: str | None = Field(description="Start in the client's timezone, if one was given")


class FreeSlots(BaseModel):
    timezone: str
    duration_minutes: int
    slots: list[Slot]


class Hold(BaseModel):
    hold_id: str
    title: str
    ref: str = Field(description="What the hold is for, e.g. a marketplace thread id")
    start_utc: str
    end_utc: str
    status: Literal["tentative", "released"]


class HoldList(BaseModel):
    holds: list[Hold]


class EmailDraft(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str
    status: Literal["draft"] = "draft"
    created_at: str


class DraftList(BaseModel):
    drafts: list[EmailDraft]


# --- storage ---------------------------------------------------------------------------------

class WorkspaceStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS holds (hold_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, ref TEXT,
                start_utc TEXT, end_utc TEXT, status TEXT);
            CREATE TABLE IF NOT EXISTS drafts (draft_id TEXT PRIMARY KEY, user_id TEXT, "to" TEXT, subject TEXT,
                body TEXT, created_at TEXT);""")
        self.lock = threading.Lock()


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _parse(ts: str) -> datetime:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError as exc:
        raise ToolFailure("invalid_datetime", f"Not an ISO datetime: {ts}") from exc
    if dt.tzinfo is None:
        raise ToolFailure("invalid_datetime", "Datetime must include a timezone offset")
    return dt.astimezone(UTC)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolFailure("invalid_timezone", f"Unknown IANA timezone: {name}") from exc


class Calendar:
    def __init__(self, store: WorkspaceStore, now: Callable[[], datetime]):
        self.store, self.now = store, now

    def busy(self, user: dict, day: date) -> list[tuple[datetime, datetime]]:
        tz = ZoneInfo(user["timezone"])
        blocks = [(datetime.combine(day, _hm(a), tz).astimezone(UTC), datetime.combine(day, _hm(b), tz).astimezone(UTC))
                  for wd, a, b, _ in user["busy"] if wd == day.weekday()]
        rows = self.store.conn.execute(
            "SELECT start_utc, end_utc FROM holds WHERE user_id = ? AND status = 'tentative'", (user["user_id"],))
        return blocks + [(datetime.fromisoformat(r[0]), datetime.fromisoformat(r[1])) for r in rows]

    def available(self, user: dict, start: datetime, end: datetime) -> str | None:
        """None if the interval is free, else the reason it isn't."""
        tz = ZoneInfo(user["timezone"])
        local_start, local_end = start.astimezone(tz), end.astimezone(tz)
        if start < self.now() + MIN_NOTICE:
            return "less than 2 hours from now"
        if local_start.weekday() not in user["workdays"] or local_start.date() != local_end.date():
            return "outside working days"
        lo, hi = _hm(user["work_hours"][0]), _hm(user["work_hours"][1])
        if local_start.time() < lo or local_end.time() > hi:
            return f"outside working hours ({user['work_hours'][0]}-{user['work_hours'][1]} {user['timezone']})"
        if any(s < end and start < e for s, e in self.busy(user, local_start.date())):
            return "overlaps another event"
        return None

    def free_slots(self, user: dict, days: int, minutes: int, earliest: datetime | None, max_slots: int,
                   per_day: int = 2) -> list[tuple[datetime, datetime]]:
        tz = ZoneInfo(user["timezone"])
        start_from = max(earliest or self.now(), self.now())
        out = []
        for i in range(days):
            day = (start_from.astimezone(tz) + timedelta(days=i)).date()
            t = datetime.combine(day, _hm(user["work_hours"][0]), tz).astimezone(UTC)
            taken = 0
            while taken < per_day and len(out) < max_slots:
                end = t + timedelta(minutes=minutes)
                if end.astimezone(tz).date() != day or end.astimezone(tz).time() > _hm(user["work_hours"][1]):
                    break
                if t >= start_from and self.available(user, t, end) is None:
                    out.append((t, end))
                    taken += 1
                    t = end + SLOT_STEP  # leave a gap so offered slots are spread out
                    continue
                t += SLOT_STEP
        return out


# --- server ----------------------------------------------------------------------------------

def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{hashlib.sha1('|'.join(parts).encode()).hexdigest()[:12]}"


def build_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    users = {u["user_id"]: u for u in settings.users}
    store = WorkspaceStore(settings.db_path)
    guard_store = GuardStore(settings.db_path.with_name(settings.db_path.stem + "_audit.sqlite3"))
    guard = ToolGuard(guard_store, RateLimiter(settings.limits), users,
                      settings.local_user or settings.users[0]["user_id"])
    cal = Calendar(store, settings.now)
    url = f"http://{settings.host}:{settings.port}"

    mcp = FastMCP(
        "gigbid-workspace",
        instructions=("The freelancer's calendar and email drafts (local mock). Find free interview slots, place "
                      "tentative holds, and save email drafts. Nothing is ever sent from here."),
        token_verifier=StaticTokenVerifier(settings.users, "workspace"),
        auth=auth_settings(url, "workspace"),
        host=settings.host, port=settings.port, stateless_http=True,
    )
    mcp.state = {"store": store, "audit": guard_store, "settings": settings}

    def _hold(r) -> Hold:
        return Hold(hold_id=r["hold_id"], title=r["title"], ref=r["ref"], start_utc=r["start_utc"],
                    end_utc=r["end_utc"], status=r["status"])

    @mcp.tool(title="Get free interview slots", annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def get_free_slots(
        ctx: Context,
        days: Annotated[int, Field(ge=1, le=14, description="How many days ahead to search")] = 5,
        duration_minutes: Annotated[int, Field(ge=15, le=120)] = 30,
        earliest: Annotated[str | None, Iso] = None,
        max_slots: Annotated[int, Field(ge=1, le=20)] = 6,
        client_timezone: Annotated[str | None, Field(description="IANA timezone, e.g. America/New_York")] = None,
    ) -> FreeSlots:
        """Free slots in the freelancer's working hours (at least 2 hours from now), at most two per day,
        avoiding meetings and existing holds. Times are shown in UTC, local time and the client's timezone."""
        args = {"days": days, "duration_minutes": duration_minutes, "earliest": earliest, "max_slots": max_slots,
                "client_timezone": client_timezone}

        async def run(user, trace):
            tz, ctz = ZoneInfo(user["timezone"]), _zone(client_timezone) if client_timezone else None
            slots = cal.free_slots(user, days, duration_minutes, _parse(earliest) if earliest else None, max_slots)
            return FreeSlots(timezone=user["timezone"], duration_minutes=duration_minutes, slots=[
                Slot(start_utc=s.isoformat(), end_utc=e.isoformat(), start_local=s.astimezone(tz).isoformat(),
                     start_client=s.astimezone(ctz).isoformat() if ctz else None) for s, e in slots])
        return await guard.run(ctx, "get_free_slots", args, run)

    @mcp.tool(title="Create tentative interview hold", annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def create_interview_hold(
        ctx: Context,
        start: Annotated[str, Iso],
        ref: Annotated[str, Field(min_length=3, max_length=80, description="What it is for, e.g. a thread id")],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_\-:.]+$")],
        duration_minutes: Annotated[int, Field(ge=15, le=120)] = 30,
        title: Annotated[str, Field(min_length=1, max_length=120)] = "Interview (tentative)",
    ) -> Hold:
        """Block a slot on the freelancer's calendar as tentative while the client confirms.
        Fails with slot_unavailable if the time is busy or outside working hours."""
        args = {"start": start, "ref": ref, "duration_minutes": duration_minutes, "title": title}

        async def run(user, trace):
            s = _parse(start)
            e = s + timedelta(minutes=duration_minutes)
            with store.lock:
                reason = cal.available(user, s, e)
                if reason:
                    raise ToolFailure("slot_unavailable", f"Cannot hold {start}: {reason}")
                hid = _id("hold", user["user_id"], idempotency_key)
                store.conn.execute("INSERT INTO holds VALUES (?, ?, ?, ?, ?, ?, 'tentative')",
                                   (hid, user["user_id"], title, ref, s.isoformat(), e.isoformat()))
                return _hold(store.conn.execute("SELECT * FROM holds WHERE hold_id = ?", (hid,)).fetchone())
        return await guard.run(ctx, "create_interview_hold", args, run, bucket="write", key=idempotency_key)

    @mcp.tool(title="Release interview hold", annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False))
    async def release_hold(
        ctx: Context,
        hold_id: Annotated[str, Field(pattern=r"^hold-[0-9a-f]{12}$")],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_\-:.]+$")],
    ) -> Hold:
        """Free a tentative hold, e.g. when the client picked another time."""
        async def run(user, trace):
            with store.lock:
                row = store.conn.execute("SELECT * FROM holds WHERE hold_id = ? AND user_id = ?",
                                         (hold_id, user["user_id"])).fetchone()
                if row is None:
                    raise ToolFailure("hold_not_found", f"No hold {hold_id}")
                store.conn.execute("UPDATE holds SET status = 'released' WHERE hold_id = ?", (hold_id,))
                return _hold(store.conn.execute("SELECT * FROM holds WHERE hold_id = ?", (hold_id,)).fetchone())
        return await guard.run(ctx, "release_hold", {"hold_id": hold_id}, run, bucket="write", key=idempotency_key)

    @mcp.tool(title="List interview holds", annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def list_holds(ctx: Context) -> HoldList:
        """Upcoming tentative holds."""
        async def run(user, trace):
            rows = store.conn.execute("SELECT * FROM holds WHERE user_id = ? AND status = 'tentative' "
                                      "AND end_utc > ? ORDER BY start_utc", (user["user_id"], settings.now().isoformat()))
            return HoldList(holds=[_hold(r) for r in rows])
        return await guard.run(ctx, "list_holds", {}, run)

    @mcp.tool(title="Create email draft", annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def create_email_draft(
        ctx: Context,
        to: Annotated[str, Field(min_length=1, max_length=200, description="Recipient name or address")],
        subject: Annotated[str, Field(min_length=1, max_length=200)],
        body: Annotated[str, Field(min_length=1, max_length=10000)],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_\-:.]+$")],
    ) -> EmailDraft:
        """Save an email as a draft for the freelancer to review and send themselves. Never sends."""
        args = {"to": to, "subject": subject, "body": body}

        async def run(user, trace):
            did = _id("draft", user["user_id"], idempotency_key)
            now = settings.now().isoformat()
            with store.lock:
                store.conn.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?)",
                                   (did, user["user_id"], to, subject, body, now))
            return EmailDraft(draft_id=did, to=to, subject=subject, body=body, created_at=now)
        return await guard.run(ctx, "create_email_draft", args, run, bucket="write", key=idempotency_key)

    @mcp.tool(title="List email drafts", annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def list_email_drafts(ctx: Context) -> DraftList:
        """Email drafts saved for the freelancer, newest first."""
        async def run(user, trace):
            rows = store.conn.execute('SELECT * FROM drafts WHERE user_id = ? ORDER BY created_at DESC',
                                      (user["user_id"],))
            return DraftList(drafts=[EmailDraft(draft_id=r["draft_id"], to=r["to"], subject=r["subject"],
                                                body=r["body"], created_at=r["created_at"]) for r in rows])
        return await guard.run(ctx, "list_email_drafts", {}, run)

    return mcp


def main() -> None:
    build_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
