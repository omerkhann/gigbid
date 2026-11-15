"""Pipeline board: proposals by status, straight from the marketplace (through MCP), joined with runs."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import Services, TraceId, User

router = APIRouter(prefix="/pipeline", tags=["proposals"])
COLUMNS = ["draft", "submitted", "viewed", "replied", "interview", "hired", "lost"]


@router.get("")
async def pipeline(user: User, svc: Services, trace_id: TraceId) -> dict:
    props = await svc.marketplace(user, "list_proposals", {}, trace_id)
    titles = {r["job_id"]: r["title"] for r in await svc.db.all(
        "SELECT job_id, title FROM runs WHERE user_id = %s AND kind = 'bid'", user["user_id"])}
    board: dict[str, list] = {c: [] for c in COLUMNS}
    for p in props["proposals"]:
        board.setdefault(p["status"], []).append({
            "proposal_id": p["proposal_id"], "job_id": p["job_id"], "title": titles.get(p["job_id"]),
            "bid_amount": p["bid_amount"], "bid_type": p["bid_type"], "thread_id": p["thread_id"],
            "updated_at": p["history"][-1]["at"] if p["history"] else None,
            "run_thread": f"bid:{user['user_id']}:{p['job_id']}"})
    return {"columns": COLUMNS, "board": board}
