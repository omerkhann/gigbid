"""Human approval and the only marketplace writes in the bid graph (R4, C5, C6).

prepare_draft  saves the draft on the marketplace (nothing is sent, no Connects spent) and gets the
               dry_run preview: exactly what would be sent and what it costs.
approve        interrupt(): the graph pauses here, checkpointed in Postgres, until the user
               approves, edits or rejects in the UI. On resume the node re-runs from the top, so
               nothing before interrupt() may have side effects.
submit         sends the approved draft. Its idempotency key is derived from the thread and the
               exact content, so if the process dies after the marketplace accepted the submit but
               before the checkpoint was saved, the resumed run sends the same key and the MCP
               server and GigSim replay the stored result: one submit, one charge.
"""

from __future__ import annotations

import hashlib
import json

from langgraph.types import interrupt

from agent.handoffs import ApprovalDecision
from agent.memory.store import record_edit
from agent.nodes.common import Ctx, node, strip_citations


def idem_key(thread_id: str, kind: str, *parts) -> str:
    digest = hashlib.sha256(json.dumps([thread_id, kind, *parts], sort_keys=True, default=str).encode()).hexdigest()
    return f"{kind}-{digest[:40]}"


def marketplace_text(draft: dict) -> tuple[str, list[str]]:
    return strip_citations(draft["cover_letter"]).strip(), [strip_citations(a).strip() for a in draft["screening_answers"]]


@node("prepare_draft")
async def prepare_draft(state: dict, ctx: Ctx) -> dict:
    d = state["proposal_draft"]
    letter, answers = marketplace_text(d)
    bid = d.get("bid_amount") or state["price_quote"]["amount"]
    if len(letter) < 50:
        return {"status": "needs_attention", "status_reason": "draft too short after compliance fixes",
                "_summary": "draft too short"}
    p = await ctx.tool("prepare_draft", "marketplace", "create_proposal_draft", {
        "job_id": state["job"]["job_id"], "cover_letter": letter, "bid_amount": bid, "screening_answers": answers,
        "idempotency_key": idem_key(ctx.thread_id, "draft", letter, answers, bid)})
    preview = await ctx.tool("prepare_draft", "marketplace", "submit_proposal", {
        "proposal_id": p["proposal_id"], "idempotency_key": idem_key(ctx.thread_id, "preview", p["proposal_id"]),
        "dry_run": True})
    update = {"marketplace_proposal_id": p["proposal_id"], "preview": preview,
              "_summary": f"draft saved, costs {preview['connects_cost']} Connects"}
    if preview["policy_violations"]:
        update.update(status="needs_attention",
                      status_reason="marketplace policy: " + ", ".join(v["rule_id"] for v in preview["policy_violations"]))
    else:
        update["status"] = "awaiting_approval"
    return update


def approval_payload(state: dict) -> dict:
    ev = state.get("evidence", {})
    return {
        "kind": "proposal_approval",
        "job": {k: state["job"].get(k) for k in ("job_id", "title", "budget_min", "budget_max", "payment_type")},
        "draft": state["proposal_draft"],
        "claims": state.get("claims", []),
        "evidence": {i: {k: e.get(k) for k in ("type", "title", "date", "outcome", "text")} for i, e in ev.items()},
        "risk": state["risk_report"], "fit": state["fit_report"], "price": state["price_quote"],
        "compliance": state.get("compliance_verdict"), "preview": state["preview"],
    }


@node("approve")
async def approve(state: dict, ctx: Ctx) -> dict:
    decision = ApprovalDecision(**interrupt(approval_payload(state)))
    if decision.action == "reject":
        return {"approval": decision.model_dump(), "status": "rejected",
                "status_reason": decision.reason or "rejected by user", "_summary": "rejected"}
    if decision.action == "edit":
        d = dict(state["proposal_draft"])
        if ctx.deps.store is not None and decision.cover_letter:   # learn from the edit
            record_edit(ctx.deps.store, state["user"]["user_id"], strip_citations(d["cover_letter"]),
                        decision.cover_letter, f"proposal:{state['job']['job_id']}:v{d.get('version', 1)}")
        d.update({k: v for k, v in {"cover_letter": decision.cover_letter, "screening_answers": decision.screening_answers,
                                     "bid_amount": decision.bid_amount}.items() if v is not None})
        d["version"] = d.get("version", 1) + 1
        d["edited_by_user"] = True
        return {"approval": decision.model_dump(), "proposal_draft": d, "status": "running",
                "_summary": "edited by user; re-checking compliance"}
    return {"approval": decision.model_dump(), "status": "running", "_summary": "approved"}


def after_approve(state: dict) -> str:
    if state.get("status") == "rejected":
        return "end"
    return "compliance" if state["approval"]["action"] == "edit" else "submit"


@node("submit")
async def submit(state: dict, ctx: Ctx) -> dict:
    letter, answers = marketplace_text(state["proposal_draft"])
    key = idem_key(ctx.thread_id, "submit", state["marketplace_proposal_id"], letter, answers,
                   state["proposal_draft"].get("bid_amount"))
    r = await ctx.tool("submit", "marketplace", "submit_proposal",
                       {"proposal_id": state["marketplace_proposal_id"], "idempotency_key": key})
    return {"submission": r, "status": "submitted", "status_reason": f"submitted; status {r['status']}",
            "_summary": f"submitted, spent {r['connects_cost']} Connects"}
