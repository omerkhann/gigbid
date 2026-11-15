"""Analytics: outcomes by category, Connects spent vs results, cost and latency per proposal,
top skip reasons. Everything comes from runs (our records) and outcome memory."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from agent.memory.store import outcome_stats
from apps.api.deps import Services, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
async def analytics(user: User, svc: Services) -> dict:
    runs = await svc.db.all("SELECT kind, status, status_reason, summary, tokens, latency_ms FROM runs WHERE user_id = %s",
                            user["user_id"])
    bids = [r for r in runs if r["kind"] == "bid"]
    submitted = [r for r in bids if r["status"] == "submitted"]
    outcomes = outcome_stats(svc.runtime.store, user["user_id"])
    replied = sum(v["replied"] + v["interview"] + v["hired"] for v in outcomes.values())
    hired = sum(v["hired"] for v in outcomes.values())
    skip_reasons = Counter((r["status_reason"] or "").split(":")[0].split(" ")[0] for r in bids
                           if r["status"] in ("skipped", "watching"))

    def p95(xs: list[int]) -> int:
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(0.95 * len(xs)))] if xs else 0

    return {
        "jobs_analysed": len(bids),
        "decisions": dict(Counter(r["status"] for r in bids)),
        "proposals_submitted": len(submitted),
        "connects_spent": sum((r["summary"] or {}).get("connects") or 0 for r in submitted),
        "reply_rate": round(replied / len(submitted), 3) if submitted else None,
        "hire_rate": round(hired / len(submitted), 3) if submitted else None,
        "by_category": outcomes,
        "per_proposal": {"tokens_avg": round(sum(r["tokens"] for r in submitted) / len(submitted)) if submitted else 0,
                         "latency_ms_p95": p95([r["latency_ms"] for r in submitted])},
        "per_job_analysed": {"latency_ms_p95": p95([r["latency_ms"] for r in bids])},
        "top_skip_reasons": skip_reasons.most_common(5),
    }
