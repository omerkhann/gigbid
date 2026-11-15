"""Job inbox, job detail, manual analysis and Scout."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import Services, TraceId, User
from apps.api.routers.runs import run_detail, run_row
from apps.api.schemas import Enqueued, RunDetail, RunRow

router = APIRouter(tags=["jobs"])


@router.get("/jobs/inbox", response_model=list[RunRow])
async def inbox(user: User, svc: Services, status: str | None = None, sort: str = Query("fit", pattern="^(fit|recent)$")):
    rows = await svc.db.all(
        "SELECT * FROM runs WHERE user_id = %s AND kind = 'bid'" + (" AND status = %s" if status else "") +
        " ORDER BY updated_at DESC LIMIT 200", *([user["user_id"], status] if status else [user["user_id"]]))
    out = [run_row(r) for r in rows]
    if sort == "fit":
        out.sort(key=lambda r: -(r.summary.get("fit") or 0))
    return out


@router.get("/jobs/{job_id}", response_model=RunDetail)
async def job_detail(job_id: str, user: User, svc: Services):
    return await run_detail(svc, user, f"bid:{user['user_id']}:{job_id}")


@router.post("/jobs/{job_id}/analyze", response_model=Enqueued, status_code=202)
async def analyze(job_id: str, user: User, svc: Services, trace_id: TraceId):
    if not job_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "Bad job id")
    queued = await svc.queue.enqueue("run_bid", user_id=user["user_id"], job_id=job_id, trace_id=trace_id,
                                     job_key=f"run_bid:{user['user_id']}:{job_id}:{trace_id}")
    return Enqueued(queued=queued is not None, thread_id=f"bid:{user['user_id']}:{job_id}", trace_id=trace_id)


@router.post("/scout/run", response_model=Enqueued, status_code=202)
async def run_scout(user: User, svc: Services, trace_id: TraceId):
    await svc.db.run("UPDATE saved_searches SET last_run_at = NULL WHERE user_id = %s", user["user_id"])
    queued = await svc.queue.enqueue("scout", user_id=user["user_id"], job_key=f"scout:{user['user_id']}:{trace_id}")
    return Enqueued(queued=queued is not None, trace_id=trace_id)
