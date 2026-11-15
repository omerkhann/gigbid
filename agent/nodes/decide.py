"""Bid / watch / skip: rules over the three reports, thresholds from config. No LLM, so every
decision is cheap, repeatable and explainable."""

from __future__ import annotations

from agent.handoffs import BidDecision
from agent.nodes.common import Ctx, node


def decide_action(job: dict, risk: dict, fit: dict, user: dict, th: dict) -> BidDecision:
    reasons = []
    if risk["score"] > th["maximum_risk_score"]:
        reasons.append(f"risk {risk['score']} > {th['maximum_risk_score']}: {', '.join(risk['flags'])}")
    bmax = job.get("budget_max")
    floor = user["hourly_floor"] if job.get("payment_type") == "hourly" else user["fixed_floor"]
    if bmax is not None and bmax < floor:
        reasons.append(f"budget {bmax} below your floor {floor}")
    if reasons:
        return BidDecision(action="skip", reasons=reasons)
    if fit["score"] < th["watch_fit_score"]:
        return BidDecision(action="skip", reasons=[(f"fit {fit['score']} < {th['watch_fit_score']}; missing: "
                                                   f"{', '.join(fit['missing_skills'][:4]) or 'evidence'}")])
    if fit["score"] < th["minimum_fit_score"]:
        return BidDecision(action="watch", reasons=[f"fit {fit['score']} is borderline (< {th['minimum_fit_score']})"])
    return BidDecision(action="bid", reasons=[f"fit {fit['score']}, risk {risk['score']}"])


@node("decide")
async def decide(state: dict, ctx: Ctx) -> dict:
    failures = state.get("branch_failures") or []
    if failures:   # one status for the thread; a marketplace outage is resumable, so it wins
        order = ["waiting_marketplace", "needs_attention", "dead_letter"]
        worst = min(failures, key=lambda f: order.index(f["status"]) if f["status"] in order else 99)
        reason = "; ".join(f["reason"] for f in failures)
        return {"status": worst["status"], "status_reason": reason, "_summary": f"stopped: {reason[:200]}"}
    d = decide_action(state["job"], state["risk_report"], state["fit_report"], state["user"],
                      ctx.deps.cfg["thresholds"])
    status = {"skip": "skipped", "watch": "watching", "bid": "running"}[d.action]
    return {"decision": d.model_dump(), "status": status, "status_reason": "; ".join(d.reasons),
            "_summary": f"{d.action}: {'; '.join(d.reasons)}"}
