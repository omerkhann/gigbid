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
