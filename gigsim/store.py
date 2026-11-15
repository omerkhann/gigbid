"""SQLite state for one GigSim run. Delete the file (or POST /admin/reset) to start over."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id   TEXT PRIMARY KEY,
    freelancer_id TEXT NOT NULL,
    job_id        TEXT NOT NULL,
    bid_amount    REAL NOT NULL,
    bid_type      TEXT NOT NULL,
    cover_letter  TEXT NOT NULL,
    answers_json  TEXT NOT NULL,
    connects_cost INTEGER,
    created_at    TEXT NOT NULL,
    submitted_at  TEXT,
    decision_json TEXT,
    UNIQUE (freelancer_id, job_id)              -- one proposal per job, as on Upwork
);

-- Status changes, including ones scheduled for the (sim) future; readers filter on at_h.
CREATE TABLE IF NOT EXISTS status_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    status      TEXT NOT NULL,
    at_h        REAL NOT NULL,                  -- sim hours since sim_start
    note        TEXT
);

CREATE TABLE IF NOT EXISTS ledger (              -- append-only Connects ledger
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    freelancer_id TEXT NOT NULL,
    delta         INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    ref           TEXT,
    at_h          REAL NOT NULL,
    UNIQUE (freelancer_id, reason, ref)
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id     TEXT PRIMARY KEY,
    proposal_id   TEXT NOT NULL UNIQUE,
    freelancer_id TEXT NOT NULL,
    job_id        TEXT NOT NULL,
    client_id     TEXT NOT NULL,
    state         TEXT NOT NULL,                -- open | interview | hired | lost
    opened_at_h   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    sender    TEXT NOT NULL,                    -- client | freelancer
    body      TEXT NOT NULL,
    at_h      REAL NOT NULL,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS idempotency (
    freelancer_id TEXT NOT NULL,
    key           TEXT NOT NULL,
    request_hash  TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    body          TEXT NOT NULL,
    PRIMARY KEY (freelancer_id, key)
);

CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, response TEXT NOT NULL);
"""


class Store:
    """Thin wrapper over one SQLite connection. `lock` serialises write paths."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()

    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    def run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, args)

    def get_meta(self, key: str, default=None):
        row = self.one("SELECT value FROM meta WHERE key = ?", (key,))
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value) -> None:
        self.run("INSERT INTO meta(key, value) VALUES(?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value)))

    def reset(self) -> None:
        with self.lock:
            for table in ("meta", "proposals", "status_events", "ledger", "threads", "messages",
                          "idempotency"):
                self.run(f"DELETE FROM {table}")  # llm_cache survives resets on purpose
