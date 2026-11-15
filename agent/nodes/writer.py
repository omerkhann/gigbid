"""Proposal Writer (strong model): cover letter + screening answers, every claim cited by evidence id.
On a revision it gets the Critic's issues. It never sets the price."""

from __future__ import annotations

import re

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import ProposalDraft, ProposalLLM
from agent.llm import prompt
from agent.nodes.analyst import job_text
from agent.nodes.common import Ctx, node, untrusted

CITED = re.compile(r"\[([A-Za-z0-9_\-]+:[^\]\s]+)\]")


def persona_header(user: dict) -> tuple[str, str]:
    from pathlib import Path

    sk = yaml.safe_load((Path(user["portfolio_dir"]) / "skeleton.yaml").read_text(encoding="utf-8"))
    return sk["name"], sk["headline"]


@node("writer")
async def writer(state: dict, ctx: Ctx) -> dict:
    job, spec = state["job"], state.get("job_spec", {})
    name, headline = persona_header(state["user"])
    evidence = list(state.get("evidence", {}).values())[:10]
    ev = "\n".join(f"- [{e['evidence_id']}] ({e['type']}, {e.get('date') or 'undated'}) {e['text'][:600]}"
                   for e in evidence) or "(no evidence found)"
    revision = ""
    if state.get("critiques"):
        last = state["critiques"][-1]
        revision = ("\n\nREVISION REQUEST from the reviewer. Fix these issues:\n"
                    + "\n".join(f"- {i}" for i in last.get("issues", []))
                    + f"\n\nPrevious draft:\n{state['proposal_draft']['cover_letter']}")
    user_msg = (f"{untrusted('job_post', job_text(job))}\n\nRequirements: {'; '.join(spec.get('requirements', []))}\n"
                f"Hidden needs: {'; '.join(spec.get('hidden_needs', [])) or 'none'}\n\nEVIDENCE (cite by id):\n{ev}"
                f"{revision}")
    out: ProposalLLM = ctx.ask("writer", ProposalLLM, [
        SystemMessage(prompt("writer").format(name=name, headline=headline)), HumanMessage(user_msg)])
    cited = sorted(set(CITED.findall(out.cover_letter + " ".join(out.screening_answers))) & set(state.get("evidence", {})))
    draft = ProposalDraft(job_id=job["job_id"], cover_letter=out.cover_letter, screening_answers=out.screening_answers,
                          evidence_ids=cited, bid_amount=state["price_quote"]["amount"],
                          version=state.get("revisions", 0) + 1)
    return {"proposal_draft": draft.model_dump(), "_summary": f"draft v{draft.version}, {len(cited)} citations"}
