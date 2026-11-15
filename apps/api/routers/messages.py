"""Client conversations: threads, messages, and asking the Client Liaison for a reply draft."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import Services, TraceId, User
from apps.api.schemas import Enqueued, Thread, Threads

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=Threads)
async def threads(user: User, svc: Services, trace_id: TraceId) -> dict:
    t = await svc.marketplace(user, "list_threads", {}, trace_id)
    runs = {r["conversation_id"]: r for r in await svc.db.all(
        "SELECT conversation_id, status, summary FROM runs WHERE user_id = %s AND kind = 'conversation'", user["user_id"])}
    for th in t["threads"]:
        r = runs.get(th["thread_id"])
        th["agent_status"] = r["status"] if r else None
        th["intent"] = (r["summary"] or {}).get("intent") if r else None
    return t


@router.get("/{conversation_id}", response_model=Thread)
async def thread(conversation_id: str, user: User, svc: Services, trace_id: TraceId) -> dict:
    t = await svc.marketplace(user, "list_messages", {"thread_id": conversation_id}, trace_id)
    thread_id = f"conv:{user['user_id']}:{conversation_id}"
    pending = None
    if await svc.db.one("SELECT 1 AS x FROM runs WHERE thread_id = %s AND status = 'awaiting_approval'", thread_id):
        pending = ((await svc.runtime.state("conversation", thread_id)).get("__interrupt__") or [None])[0]
    return {**t, "run_thread": thread_id, "pending_reply": pending}


@router.post("/{conversation_id}/draft", response_model=Enqueued, status_code=202)
async def draft(conversation_id: str, user: User, svc: Services, trace_id: TraceId):
    queued = await svc.queue.enqueue("run_conversation", user_id=user["user_id"], conversation_id=conversation_id,
                                     trace_id=trace_id, job_key=f"run_conversation:{user['user_id']}:{conversation_id}:{trace_id}")
    return Enqueued(queued=queued is not None, thread_id=f"conv:{user['user_id']}:{conversation_id}", trace_id=trace_id)
