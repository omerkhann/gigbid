"""App database (Postgres): users, sessions, encrypted tokens, saved searches, seen jobs, runs.

LangGraph's checkpoints and memory store live in the same database in their own tables (created
by the LangGraph savers). Every query here filters by user_id: tenant scoping (assignment E4).
"""

from __future__ import annotations

import json
import os
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    password     TEXT NOT NULL,                       -- scrypt hash
    persona      TEXT,                                -- portfolio folder under data/personas, or NULL
    settings     JSONB NOT NULL DEFAULT '{}'::jsonb,  -- floors, autonomy, budgets
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
    expires_at   TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (               -- encrypted (Fernet); never logged
    user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
    provider     TEXT NOT NULL,                       -- marketplace_mcp | portfolio_mcp | workspace_mcp | upwork
    ciphertext   TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider)
);
CREATE TABLE IF NOT EXISTS saved_searches (
    search_id    TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
    query        JSONB NOT NULL,                      -- search_jobs arguments
    every_minutes INT NOT NULL DEFAULT 60,
    last_run_at  TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS seen_jobs (                 -- Scout dedup
    user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
    job_id       TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,                       -- normalised title + description
    duplicate_of TEXT,
    seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS seen_jobs_fp ON seen_jobs (user_id, fingerprint);
CREATE TABLE IF NOT EXISTS runs (                      -- one row per graph thread
    thread_id    TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
    kind         TEXT NOT NULL,                       -- bid | conversation
    job_id       TEXT,
    conversation_id TEXT,
    title        TEXT,
    status       TEXT NOT NULL,
    status_reason TEXT,
    summary      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- fit, risk, decision, price for the inbox
    trace_id     TEXT,
    tokens       INT NOT NULL DEFAULT 0,
    latency_ms   INT NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS runs_user ON runs (user_id, updated_at DESC);
"""


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5433/gigbid")


class Db:
    def __init__(self, url: str | None = None):
        self.url = url or database_url()
        self.pool = AsyncConnectionPool(self.url, open=False, kwargs={"row_factory": dict_row, "autocommit": True})

    async def open(self) -> Db:
        await self.pool.open()
        async with self.pool.connection() as c:
            await c.execute(SCHEMA)
        return self

    async def close(self) -> None:
        await self.pool.close()

    async def all(self, sql: str, *args) -> list[dict[str, Any]]:
        async with self.pool.connection() as c:
            return await (await c.execute(sql, args)).fetchall()

    async def one(self, sql: str, *args) -> dict[str, Any] | None:
        async with self.pool.connection() as c:
            return await (await c.execute(sql, args)).fetchone()

    async def run(self, sql: str, *args) -> None:
        async with self.pool.connection() as c:
            await c.execute(sql, args)

    async def upsert_run(self, row: dict[str, Any]) -> None:
        await self.run(
            "INSERT INTO runs (thread_id, user_id, kind, job_id, conversation_id, title, status, status_reason, summary, "
            "trace_id, tokens, latency_ms) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (thread_id) DO UPDATE SET status = EXCLUDED.status, status_reason = EXCLUDED.status_reason, "
            "summary = EXCLUDED.summary, title = COALESCE(EXCLUDED.title, runs.title), trace_id = EXCLUDED.trace_id, "
            "tokens = runs.tokens + EXCLUDED.tokens, latency_ms = runs.latency_ms + EXCLUDED.latency_ms, updated_at = now()",
            row["thread_id"], row["user_id"], row["kind"], row.get("job_id"), row.get("conversation_id"), row.get("title"),
            row["status"], row.get("status_reason"), json.dumps(row.get("summary", {})), row.get("trace_id"),
            row.get("tokens", 0), row.get("latency_ms", 0))
