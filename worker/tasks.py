"""Background work (assignment E1): graph runs, resumes after approval, scheduled Scout, outcome polling.

Graph runs never happen inside a web request. Every task is idempotent:
- graph runs resume from Postgres checkpoints, and marketplace writes carry idempotency keys,
  so a task retried after a worker crash never double-submits;
- Scout records every job it has seen (by id and by a text fingerprint), so a restart never
  re-analyses a job.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

from agent.llm import config as agent_config
from agent.memory.store import record_outcome
from agent.runtime import run_summary
from apps.api.auth.security import decrypt
from pipelines.parsing import normalise_for_dedup

# Budget guard: analyse at most this many new jobs per scheduled run (env override; the VM sets 2 so
# hourly scouting stays inside the hosted free-tier daily quota, docs/RUNBOOK.md "Free-tier caps").
MAX_NEW_JOBS_PER_SCOUT = int(os.environ.get("MAX_NEW_JOBS_PER_SCOUT", "5"))
PROVIDERS = {"marketplace": "marketplace_mcp", "portfolio": "portfolio_mcp", "workspace": "workspace_mcp"}


# --- helpers ---------------------------------------------------------------------------------------

async def load_user(ctx: dict, user_id: str) -> tuple[dict, dict[str, str]]:
    db = ctx["db"]
    user = await db.one("SELECT user_id, email, name, persona, settings FROM users WHERE user_id = %s", user_id)
    rows = await db.all("SELECT provider, ciphertext FROM credentials WHERE user_id = %s", user_id)
    by_provider = {r["provider"]: decrypt(r["ciphertext"]) for r in rows}
    tokens = {name: by_provider[p] for name, p in PROVIDERS.items() if p in by_provider}
    return user, tokens


def publisher(ctx: dict, user_id: str):
    async def publish(event: dict) -> None:
        await ctx["events"].publish(user_id, {**event, "at": datetime.now(UTC).isoformat()})
    return publish


async def record(ctx: dict, user: dict, kind: str, thread: str, values: dict, trace_id: str | None, **extra) -> dict:
    await ctx["db"].upsert_run({
        "thread_id": thread, "user_id": user["user_id"], "kind": kind, "status": values.get("status") or "running",
        "status_reason": values.get("status_reason"), "summary": run_summary(kind, values), "trace_id": trace_id,
        "tokens": values.get("tokens") or 0, "latency_ms": values.get("_latency_ms", 0), **extra})
    return {"thread_id": thread, "status": values.get("status")}


def fingerprint(job: dict) -> str:
    return hashlib.sha1(normalise_for_dedup(f"{job['title']} {job.get('description_preview', '')}")[:400]
                        .encode()).hexdigest()


# --- graph tasks ---------------------------------------------------------------------------------

async def run_bid(ctx: dict, user_id: str, job_id: str, trace_id: str | None = None) -> dict:
    user, tokens = await load_user(ctx, user_id)
    trace_id = trace_id or uuid.uuid4().hex
    gateway = ctx["runtime"].config(user, "scout", trace_id, tokens)["configurable"]["deps"].gateway
    job = await gateway.call("scout", "marketplace", "get_job", {"job_id": job_id}, trace_id)
    values = await ctx["runtime"].run_bid(user, job, tokens, publisher(ctx, user_id), trace_id)
    return await record(ctx, user, "bid", f"bid:{user_id}:{job_id}", values, trace_id, job_id=job_id, title=job["title"])


async def resume_bid(ctx: dict, user_id: str, thread_id: str, decision: dict, trace_id: str | None = None) -> dict:
    user, tokens = await load_user(ctx, user_id)
    values = await ctx["runtime"].resume_bid(user, thread_id, decision, tokens, publisher(ctx, user_id), trace_id)
    return await record(ctx, user, "bid", thread_id, values, trace_id)


async def run_conversation(ctx: dict, user_id: str, conversation_id: str, trace_id: str | None = None) -> dict:
    user, tokens = await load_user(ctx, user_id)
    values = await ctx["runtime"].run_conversation(user, conversation_id, tokens, publisher(ctx, user_id), trace_id)
    return await record(ctx, user, "conversation", f"conv:{user_id}:{conversation_id}", values, trace_id,
                        conversation_id=conversation_id, title=(values.get("job") or {}).get("title"))


async def resume_conversation(ctx: dict, user_id: str, thread_id: str, decision: dict, trace_id: str | None = None) -> dict:
    user, tokens = await load_user(ctx, user_id)
    values = await ctx["runtime"].resume_conversation(user, thread_id, decision, tokens, publisher(ctx, user_id), trace_id)
    return await record(ctx, user, "conversation", thread_id, values, trace_id)


# --- scheduled tasks -----------------------------------------------------------------------------

async def scout(ctx: dict, user_id: str) -> dict:
    """Run the user's due saved searches, dedupe, and queue new jobs for analysis."""
    db, queue = ctx["db"], ctx["queue"]
    user, tokens = await load_user(ctx, user_id)
    trace_id = uuid.uuid4().hex
    gateway = ctx["runtime"].config(user, "scout", trace_id, tokens)["configurable"]["deps"].gateway
    now = datetime.now(UTC)
    searches = await db.all("SELECT * FROM saved_searches WHERE user_id = %s", user_id)
    queued, dupes = [], 0
    for s in searches:
        every = s["every_minutes"]
        if agent_config()["marketplace"]["mode"] == "upwork_live":
            every = max(every, 60)              # live Upwork: at most hourly, whatever is stored
        if s["last_run_at"] and s["last_run_at"] + timedelta(minutes=every) > now:
            continue
        query = dict(s["query"])
        page = await gateway.call("scout", "marketplace", "search_jobs", {**query, "limit": 20}, trace_id)
        for job in page["jobs"]:
            if len(queued) >= MAX_NEW_JOBS_PER_SCOUT:
                break
            if not job["open"] or await db.one("SELECT 1 AS x FROM seen_jobs WHERE user_id=%s AND job_id=%s",
                                               user_id, job["job_id"]):
                continue
            fp = fingerprint(job)
            dup = await db.one("SELECT job_id FROM seen_jobs WHERE user_id=%s AND fingerprint=%s", user_id, fp)
            await db.run("INSERT INTO seen_jobs (user_id, job_id, fingerprint, duplicate_of) VALUES (%s,%s,%s,%s) "
                         "ON CONFLICT DO NOTHING", user_id, job["job_id"], fp, dup["job_id"] if dup else None)
            if dup:
                dupes += 1
                continue
            await queue.enqueue("run_bid", user_id=user_id, job_id=job["job_id"], trace_id=trace_id,
                                job_key=f"run_bid:{user_id}:{job['job_id']}")
            queued.append(job["job_id"])
        await db.run("UPDATE saved_searches SET last_run_at = %s WHERE search_id = %s", now, s["search_id"])
    return {"queued": queued, "duplicates": dupes}


async def poll_outcomes(ctx: dict, user_id: str) -> dict:
    """Pull proposal statuses into outcome memory; start a conversation run for new client messages."""
    db, queue = ctx["db"], ctx["queue"]
    user, tokens = await load_user(ctx, user_id)
    trace_id = uuid.uuid4().hex
    gateway = ctx["runtime"].config(user, "client_liaison", trace_id, tokens)["configurable"]["deps"].gateway
    gateway.allowlist = {**gateway.allowlist, "poll": {("marketplace", "list_proposals"), ("marketplace", "list_threads")}}
    props = await gateway.call("poll", "marketplace", "list_proposals", {}, trace_id)
    ours = {r["job_id"]: r for r in await db.all(
        "SELECT job_id, summary FROM runs WHERE user_id=%s AND kind='bid' AND status='submitted'", user_id)}
    recorded = 0
    store = ctx["runtime"].store
    for p in props["proposals"]:
        key = f"{p['proposal_id']}:{p['status']}"
        if p["job_id"] in ours and store.get(("outcome_seen", user_id), key) is None:
            job = (await db.one("SELECT title FROM runs WHERE thread_id=%s", f"bid:{user_id}:{p['job_id']}")) or {}
            category = (ours[p["job_id"]]["summary"] or {}).get("category") or "all"
            if record_outcome(store, user_id, category, p["status"], True):
                store.put(("outcome_seen", user_id), key, {"title": job.get("title")})
                recorded += 1
    threads = await gateway.call("poll", "marketplace", "list_threads", {}, trace_id)
    started = []
    for t in threads["threads"]:
        if not t["accepting_messages"]:
            continue
        run = await db.one("SELECT status FROM runs WHERE thread_id=%s", f"conv:{user_id}:{t['thread_id']}")
        if run and run["status"] in ("awaiting_approval", "running"):
            continue      # already being handled
        await queue.enqueue("run_conversation", user_id=user_id, conversation_id=t["thread_id"], trace_id=trace_id,
                            job_key=f"run_conversation:{user_id}:{t['thread_id']}:{json.dumps(t['status'])}")
        started.append(t["thread_id"])
    return {"outcomes_recorded": recorded, "conversations_started": started}


TASKS = {f.__name__: f for f in (run_bid, resume_bid, run_conversation, resume_conversation, scout, poll_outcomes)}
