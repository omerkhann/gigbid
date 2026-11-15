"""Claim verification (assignment B3): split a draft into claims, check each against the cited
evidence, and remove or soften unsupported ones BEFORE the Critic sees the draft.

`verify_claims(ask, draft, evidence)` uses a strong model; `ask` is the node's structured caller.
Returns (claims, revised_letter). The unsupported rate before and after is reported by the caller.
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import Claim, ClaimCheckLLM
from agent.llm import prompt


def verify_claims(ask: Callable, draft: str, evidence: dict[str, dict]) -> tuple[list[Claim], str]:
    ev = "\n".join(f"- [{e['evidence_id']}] {e['text'][:800]}" for e in evidence.values()) or "(none)"
    out: ClaimCheckLLM = ask([SystemMessage(prompt("verify_claims")),
                              HumanMessage(f"EVIDENCE:\n{ev}\n\nDRAFT:\n{draft}")])
    return out.claims, out.revised_cover_letter
