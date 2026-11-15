"""Approvals: everything waiting for the human, and approve / edit / reject.

A decision is not executed in the request: it is queued for the worker, which resumes the
checkpointed graph thread. A page refresh never loses a pending approval (it lives in Postgres),
and a double-click can't send twice (the queue key and the marketplace idempotency keys).
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException

from apps.api.deps import Services, TraceId, User
from apps.api.routers.runs import run_detail, run_row
from apps.api.schemas import ApprovalIn, Enqueued, RegenerateIn, RegenerateOut, RunDetail, RunRow

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[RunRow])
async def pending(user: User, svc: Services):
    rows = await svc.db.all("SELECT * FROM runs WHERE user_id = %s AND status = 'awaiting_approval' "
                            "ORDER BY updated_at DESC", user["user_id"])
    return [run_row(r) for r in rows]


@router.get("/{thread_id}", response_model=RunDetail)
async def get_approval(thread_id: str, user: User, svc: Services):
    d = await run_detail(svc, user, thread_id)
    if d.pending_approval is None:
        raise HTTPException(409, "Nothing is waiting for approval on this run")
    return d


@router.post("/{thread_id}", response_model=Enqueued, status_code=202)
async def decide(thread_id: str, body: ApprovalIn, user: User, svc: Services, trace_id: TraceId):
    row = await svc.db.one("SELECT kind, status FROM runs WHERE thread_id = %s AND user_id = %s", thread_id, user["user_id"])
    if row is None:
        raise HTTPException(404, "No such run")
    if row["status"] != "awaiting_approval":
        raise HTTPException(409, f"Run is {row['status']}, not awaiting approval")
    if body.action == "edit" and not (body.cover_letter or body.screening_answers or body.bid_amount):
        raise HTTPException(422, "An edit needs the edited text or bid")
    decision = body.model_dump(exclude_none=True)
    digest = hashlib.sha256(json.dumps(decision, sort_keys=True).encode()).hexdigest()[:16]
    task = "resume_bid" if row["kind"] == "bid" else "resume_conversation"
    await svc.db.run("UPDATE runs SET status = 'running', updated_at = now() WHERE thread_id = %s", thread_id)
    queued = await svc.queue.enqueue(task, user_id=user["user_id"], thread_id=thread_id, decision=decision,
                                     trace_id=trace_id, job_key=f"{task}:{thread_id}:{digest}")
    return Enqueued(queued=queued is not None, thread_id=thread_id, trace_id=trace_id)


@router.post("/{thread_id}/regenerate", response_model=RegenerateOut)
async def regenerate(thread_id: str, body: RegenerateIn, user: User, svc: Services):
    """Rewrite one paragraph of a pending proposal with the Writer model and the same evidence. Returns
    text only: the user applies it as an edit, which re-runs compliance before anything is sent."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel

    from agent.llm import prompt, structured
    from agent.nodes.analyst import job_text
    from agent.nodes.common import untrusted
    from agent.nodes.writer import persona_header
    from agent.runtime import user_profile

    d = await run_detail(svc, user, thread_id)
    if d.kind != "bid" or d.pending_approval is None:
        raise HTTPException(409, "Only a proposal waiting for approval can be regenerated")

    class Paragraph(BaseModel):
        text: str

    name, headline = persona_header(user_profile(user))
    ev = "\n".join(f"- [{i}] {e['text'][:500]}" for i, e in (d.state.get("evidence") or {}).items())
    ask = (svc.runtime.llm or structured)("writer", Paragraph)
    out, _ = ask([SystemMessage(prompt("regenerate").format(name=name, headline=headline)),
                  HumanMessage(f"{untrusted('job_post', job_text(d.state['job']))}\n\nEVIDENCE:\n{ev}\n\n"
                               f"PARAGRAPH:\n{body.paragraph}\n\nINSTRUCTION: {body.instruction or 'make it stronger'}")])
    return RegenerateOut(text=out.text.strip())
