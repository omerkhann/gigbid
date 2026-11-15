"""Compliance Guard: policy rules from agent/compliance_rules.yaml (config, so a policy change is a
config edit). Rules either fix the draft (drop the offending sentence) or block it with a reason.
Runs after the Critic and again after any human edit."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from agent.handoffs import ComplianceVerdict
from agent.nodes.common import Ctx, node, strip_citations
from mcp_servers.common.pii import mask_text

RULES_PATH = Path(__file__).resolve().parents[1] / "compliance_rules.yaml"
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@lru_cache(maxsize=1)
def rules() -> list[dict]:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))["rules"]


def _hits(rule: dict, sentence: str, evidence_text: str, unsupported: list[str]) -> bool:
    low = sentence.lower()
    d = rule["detector"]
    if d == "contact_details":
        return mask_text(sentence) != sentence
    if d == "keywords":
        return any(k in low for k in rule["keywords"])
    if d == "keywords_unless_evidenced":
        return any(k in low and k not in evidence_text for k in rule["keywords"])
    if d == "unsupported_claims":
        return any(c and c.lower() in low for c in unsupported)
    return False


def check(text: str, evidence_text: str, unsupported: list[str]) -> tuple[str, list[str], list[str]]:
    """Returns (fixed_text, fixed_rule_ids, blocking_rule_ids)."""
    kept, fixed, blocked = [], set(), set()
    for sentence in SENTENCE.split(text):
        drop = False
        for rule in rules():
            if _hits(rule, strip_citations(sentence), evidence_text, unsupported):
                if rule["action"] == "block":
                    blocked.add(rule["id"])
                else:
                    fixed.add(rule["id"])
                    drop = True
        if not drop and sentence.strip():
            kept.append(sentence.strip())
    return " ".join(kept), sorted(fixed), sorted(blocked)


@node("compliance")
async def compliance(state: dict, ctx: Ctx) -> dict:
    d = dict(state["proposal_draft"])
    evidence_text = " ".join(e["text"] for e in state.get("evidence", {}).values()).lower()
    unsupported = [c["claim"] for c in state.get("claims", []) if c["verdict"] == "unsupported"]
    letter, f1, b1 = check(d["cover_letter"], evidence_text, unsupported)
    answers, fixed, blocked = [], set(f1), set(b1)
    for a in d["screening_answers"]:
        t, f, b = check(a, evidence_text, unsupported)
        answers.append(t)
        fixed |= set(f)
        blocked |= set(b)
    if blocked:
        v = ComplianceVerdict(status="block", violations=sorted(blocked | fixed),
                              reason=f"blocked by: {', '.join(sorted(blocked))}")
        return {"compliance_verdict": v.model_dump(), "status": "needs_attention", "status_reason": v.reason,
                "_summary": v.reason}
    status = "fixed" if fixed else "pass"
    if fixed:
        d.update(cover_letter=letter, screening_answers=answers)
    v = ComplianceVerdict(status=status, violations=sorted(fixed), fixed_cover_letter=letter if fixed else None,
                          reason="removed: " + ", ".join(sorted(fixed)) if fixed else "no issues")
    return {"compliance_verdict": v.model_dump(), "proposal_draft": d,
            "_summary": "pass: no issues" if not fixed else f"fixed: removed {', '.join(sorted(fixed))}"}
