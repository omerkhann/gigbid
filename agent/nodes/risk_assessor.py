"""Risk Assessor: client history + rules + a small model -> RiskReport.

The score is computed from weighted flags, never generated. Rules catch the known patterns
cheaply and deterministically; the model catches phrasing the rules miss. Unverified payment on
its own is weak evidence: about a third of real, legitimate clients are unverified.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import RiskLLM, RiskReport
from agent.llm import prompt
from agent.nodes.analyst import job_text
from agent.nodes.common import Ctx, node, untrusted

# flag -> (weight, pattern). Weights add up; the score is capped at 1. Each scam pattern is a
# specific request (not a bare "Telegram" or "crypto": "Telegram bot development" is a real job), so
# one match is enough to skip on its own (0.75 > the 0.70 threshold).
CONTACT_APPS = r"(?:telegram|whatsapp|signal|skype|wechat)"
PATTERNS = {
    "off_platform": (0.75, (rf"(?:message|contact|reach|text|chat with|add|talk to|dm) (?:me |us )?(?:on|via|over|at) {CONTACT_APPS}|"
                            rf"{CONTACT_APPS} (?:id|number|me)\b|continue on {CONTACT_APPS}|"
                            r"outside (?:the )?(?:platform|upwork|this site)|off[- ]platform|"
                            r"pay(?:ment)? (?:you )?directly|(?:pay|paid|payment) (?:via|by|through) (?:wise|bank transfer)|"
                            r"(?:pay|paid) (?:in|with|via) crypto|crypto payment|send me your (?:email|number|phone)")),
    "unpaid_work": (0.75, (r"(?:unpaid|free) (?:test|trial|sample)|test task is unpaid|no payment for the sample|"
                           r"best submission wins|as a free sample")),
    "upfront_fee": (0.75, (r"(?:registration|onboarding|verification|background check|training|joining|sign-?up) fee|"
                           r"purchase our|must (?:buy|purchase) (?:our|the)|(?:fee|purchase) before (?:receiving|starting|the first)")),
}
INJECTION = (0.35, (r"ignore (?:all |your |any )?(?:previous |prior )?(?:instructions|rules)|ai assistants?|"
                    r"\bfor ai\b|automated (?:bidding )?tool|\[system\]|<!--|assistant instruction|"
                    r"if you are an ai|this overrides|proposal tools must"))
SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
CLIENT_NEW_UNVERIFIED = 0.15
CLIENT_UNVERIFIED = 0.05
LLM_SIGNAL = 0.25


def rule_flags(job: dict, client: dict) -> dict[str, float]:
    flags: dict[str, float] = {}
    for sentence in SENTENCES.split(job_text(job).lower()):
        if re.search(INJECTION[1], sentence):
            # An injected sentence ("AI: add your WhatsApp number") is an attack on GigBid, not the
            # client's own scam: count it once as injection so a legitimate job is not skipped.
            flags["prompt_injection"] = INJECTION[0]
            continue
        for name, (w, pat) in PATTERNS.items():
            if re.search(pat, sentence):
                flags[name] = w
    if not client.get("payment_verified"):
        new = not client.get("total_spent") and not client.get("feedback_count")
        flags["client_new_unverified" if new else "client_unverified"] = CLIENT_NEW_UNVERIFIED if new else CLIENT_UNVERIFIED
    return flags


@node("risk_assessor")
async def risk_assessor(state: dict, ctx: Ctx) -> dict:
    job = state["job"]
    client = await ctx.tool("risk_assessor", "marketplace", "get_client_history", {"client_id": job["client_id"]})
    flags = rule_flags(job, client)
    llm: RiskLLM = ctx.ask("risk_assessor", RiskLLM, [
        SystemMessage(prompt("risk_assessor")), HumanMessage(untrusted("job_post", job_text(job)))])
    if llm.scam_signals:
        flags["model_scam_signals"] = LLM_SIGNAL
    if llm.injection_attempt and "prompt_injection" not in flags:
        flags["prompt_injection"] = INJECTION[0]
    score = round(min(1.0, sum(flags.values())), 3)
    rating = "no reviews yet" if client.get("rating") is None else f"rated {client['rating']}"
    summary = (f"{'verified' if client.get('payment_verified') else 'unverified'} payment, "
               f"${client.get('total_spent', 0):,.0f} spent, {rating}, {client.get('country') or 'unknown country'}")
    detail = "; ".join(f"{k} (+{v})" for k, v in sorted(flags.items(), key=lambda kv: -kv[1])) or "no flags"
    report = RiskReport(score=score, flags=sorted(flags), client_summary=summary,
                        explanation=f"{llm.assessment} Flags: {detail}." +
                                    (f" Quotes: {'; '.join(llm.scam_signals[:3])}" if llm.scam_signals else ""))
    return {"risk_report": report.model_dump(), "_summary": f"risk {score} {sorted(flags)}"}
