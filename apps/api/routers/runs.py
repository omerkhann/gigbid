"""Runs (graph threads): list, detail, and the live event stream (Server-Sent Events)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent.tracing import trace_link
from apps.api.deps import Services, User
from apps.api.schemas import RunDetail, RunRow

router = APIRouter(prefix="/runs", tags=["runs"])
HIDDEN_STATE = {"user"}          # never echo internal config back to the browser


def run_row(r: dict) -> RunRow:
    return RunRow(**{**r, "updated_at": r["updated_at"].isoformat()})


async def run_detail(svc, user: dict, thread_id: str) -> RunDetail:
    row = await svc.db.one("SELECT * FROM runs WHERE thread_id = %s AND user_id = %s", thread_id, user["user_id"])
    if row is None:
        raise HTTPException(404, "No such run")
    values = await svc.runtime.state(row["kind"], thread_id)
    pending = (values.pop("__interrupt__", None) or [None])[0]
    return RunDetail(thread_id=thread_id, kind=row["kind"], status=row["status"], status_reason=row["status_reason"],
                     trace_id=row["trace_id"], trace_url=trace_link(thread_id), events=values.pop("events", []) or [],
                     state={k: v for k, v in values.items() if k not in HIDDEN_STATE}, pending_approval=pending)


@router.get("", response_model=list[RunRow])
async def list_runs(user: User, svc: Services, limit: int = 50):
    rows = await svc.db.all("SELECT * FROM runs WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
                            user["user_id"], min(limit, 200))
    return [run_row(r) for r in rows]


@router.get("/stream")
async def stream(request: Request, user: User, svc: Services):
    """Live node-by-node progress for all of the user's runs (text/event-stream)."""
    async def events():
        yield "event: hello\ndata: {}\n\n"
        sub = svc.events.subscribe(user["user_id"])
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(sub.__anext__(), timeout=15)
                yield f"data: {json.dumps(event, default=str)}\n\n"
            except TimeoutError:
                yield ": keep-alive\n\n"
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{thread_id}", response_model=RunDetail)
async def get_run(thread_id: str, user: User, svc: Services):
    return await run_detail(svc, user, thread_id)
