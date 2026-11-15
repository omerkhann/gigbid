"""verify_claims and Critic nodes.

verify_claims runs first (assignment B3: unsupported claims are removed before the Critic sees the
draft). The Critic then scores grounding, personalisation, clarity and length and can send the
draft back to the Writer at most `max_revisions` times (C4).
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import ClaimCheckLLM, Critique
from agent.llm import prompt
from agent.nodes.analyst import job_text
from agent.nodes.common import Ctx, node, untrusted
from rag.verify import verify_claims as check


@node("verify_claims")
async def verify_claims(state: dict, ctx: Ctx) -> dict:
    draft = dict(state["proposal_draft"])
    claims, revised = check(lambda msgs: ctx.ask("verify_claims", ClaimCheckLLM, msgs),
                            draft["cover_letter"], state.get("evidence", {}))
    unsupported = [c for c in claims if c.verdict == "unsupported"]
    draft.update(cover_letter=revised or draft["cover_letter"],
                 unsupported_before=len(unsupported), claims_total=len(claims))
    return {"proposal_draft": draft, "claims": [c.model_dump() for c in claims],
            "_summary": f"{len(claims)} claims, {len(unsupported)} unsupported removed"}


@node("critic")
async def critic(state: dict, ctx: Ctx) -> dict:
    d = state["proposal_draft"]
    answers = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(d["screening_answers"])) or "none"
    c: Critique = ctx.ask("critic", Critique, [
        SystemMessage(prompt("critic")),
        HumanMessage(f"{untrusted('job_post', job_text(state['job']))}\n\nCOVER LETTER:\n{d['cover_letter']}\n\n"
                     f"SCREENING ANSWERS:\n{answers}")])
    revisions = state.get("revisions", 0)
    send_back = c.verdict == "revise" and revisions < ctx.deps.cfg["budgets"]["max_revisions"]
    update = {"critiques": [c.model_dump()], "revise_requested": send_back,
              "_summary": f"{c.verdict} {c.scores}" + (" -> revise" if send_back else "")}
    if send_back:
        update["revisions"] = revisions + 1
    return update


def after_critic(state: dict) -> str:
    """Route: back to the Writer only if the Critic asked for a revision and the budget allowed it."""
    return "writer" if state.get("revise_requested") else "compliance"
