"""Per-user rate limiting, idempotency records and the append-only audit log."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from mcp_servers.common.pii import mask

SCHEMA = """
CREATE TABLE IF NOT EXISTS idempotency (
    user_id TEXT NOT NULL, tool TEXT NOT NULL, key TEXT NOT NULL,
    args_hash TEXT NOT NULL, result TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (user_id, tool, key)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL, user_id TEXT NOT NULL, tool TEXT NOT NULL,
    args TEXT NOT NULL, result TEXT, status TEXT NOT NULL, trace_id TEXT NOT NULL
);
-- Append-only: the database itself refuses edits and deletes.
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
    BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
    BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


class RateLimited(Exception):
    pass


class RateLimiter:
    """Sliding one-minute window per (user, bucket). Waits politely up to `max_wait` seconds
    rather than letting requests hit the marketplace's own limit."""

    def __init__(self, limits: dict[str, int], max_wait: float = 30.0):
        self.limits, self.max_wait = limits, max_wait
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def acquire(self, user: str, bucket: str) -> None:
        limit = self.limits[bucket]
        waited = 0.0
        while True:
            async with self.lock:
                now = time.monotonic()
                q = self.hits[(user, bucket)]
                while q and now - q[0] >= 60:
                    q.popleft()
                if len(q) < limit:
                    q.append(now)
                    return
                wait = 60 - (now - q[0])
            if waited + wait > self.max_wait:
                raise RateLimited(f"{bucket} limit of {limit}/min reached; retry in {wait:.0f}s")
            await asyncio.sleep(wait)
            waited += wait


def args_hash(args: dict) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()


class GuardStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def replay(self, user: str, tool: str, key: str, ahash: str) -> dict | None:
        """Stored result for this key, or None. Raises ValueError if the key was used for other args."""
        with self.lock:
            row = self.conn.execute("SELECT args_hash, result FROM idempotency WHERE user_id=? AND tool=? AND key=?",
                                    (user, tool, key)).fetchone()
        if row is None:
            return None
        if row[0] != ahash:
            raise ValueError("idempotency key already used for a different request")
        return json.loads(row[1])

    def remember(self, user: str, tool: str, key: str, ahash: str, result: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO idempotency VALUES (?, ?, ?, ?, ?, ?)",
                              (user, tool, key, ahash, json.dumps(result), time.time()))

    def audit(self, user: str, tool: str, args: dict, result, status: str, trace_id: str) -> None:
        text = None if result is None else json.dumps(mask(result), default=str)[:4000]
        with self.lock:
            self.conn.execute("INSERT INTO audit(ts, user_id, tool, args, result, status, trace_id) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (time.time(), user, tool, json.dumps(mask(args), default=str), text, status, trace_id))

    def audit_rows(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM audit ORDER BY id")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


# --- The per-call pipeline shared by every GigBid MCP server --------------------------------

class ToolFailure(Exception):
    """A definite, reportable failure. Becomes {"error": code, "detail": ..., **extra} for the caller."""

    def __init__(self, code: str, detail: str, status: int | None = None, extra: dict | None = None):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status, self.extra = code, detail, status, extra or {}


class ToolGuard:
    """identity -> trace id -> rate limit -> idempotency replay -> call -> audit.

    `users` maps user_id -> user record. Over HTTP the bearer token picks the user; in stdio or
    in-memory use there is no token, so `local_user` is used.
    """

    def __init__(self, store: GuardStore, limiter: RateLimiter, users: dict[str, dict], local_user: str):
        self.store, self.limiter, self.users, self.local_user = store, limiter, users, local_user

    def identity(self) -> dict:
        from mcp.server.auth.middleware.auth_context import get_access_token
        token = get_access_token()
        return self.users[token.client_id] if token else self.users[self.local_user]

    @staticmethod
    def trace_id(ctx) -> str:
        import uuid
        meta = ctx.request_context.meta
        return str((meta.model_extra or {}).get("trace_id") if meta else "") or uuid.uuid4().hex

    async def run(self, ctx, tool: str, args: dict, fn, bucket: str = "read", key: str | None = None):
        from mcp.server.fastmcp.exceptions import ToolError
        from pydantic import BaseModel

        user, trace = self.identity(), self.trace_id(ctx)
        uid = user["user_id"]
        try:
            await self.limiter.acquire(uid, bucket)
        except RateLimited as exc:
            self.store.audit(uid, tool, args, None, "rate_limited", trace)
            raise ToolError(json.dumps({"error": "rate_limited", "detail": str(exc)})) from exc
        ahash = args_hash(args)
        if key:
            try:
                stored = self.store.replay(uid, tool, key, ahash)
            except ValueError as exc:
                self.store.audit(uid, tool, args, None, "key_reused", trace)
                raise ToolError(json.dumps({"error": "idempotency_key_reused", "detail": str(exc)})) from exc
            if stored is not None:
                self.store.audit(uid, tool, args, stored, "replayed", trace)
                return stored
        try:
            result = await fn(user, trace)
        except ToolFailure as exc:
            self.store.audit(uid, tool, args, {"error": exc.code, "detail": exc.detail}, "error", trace)
            raise ToolError(json.dumps({"error": exc.code, "detail": exc.detail, **exc.extra})) from exc
        data = result.model_dump() if isinstance(result, BaseModel) else result
        if key:
            self.store.remember(uid, tool, key, ahash, data)
        self.store.audit(uid, tool, args, data, "ok", trace)
        return result
