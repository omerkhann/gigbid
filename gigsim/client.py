"""Simulated clients.

Two modes behind the same two functions:
  heuristic - deterministic keyword scoring. No API key; used in CI and unit tests.
  llm       - one LLM call per decision (added in build step 5), cached in SQLite.

Both apply the same hard rule first: a bid above budget_ceiling x tolerance is never answered.
"""

from __future__ import annotations

import re

_STOP = {"a", "an", "the", "for", "and", "to", "of", "in", "on", "with", "need", "needed",
         "looking", "expert", "help", "i", "we", "my", "our", "-", "&", "/"}
_SLOT = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\butc\b",
                   re.IGNORECASE)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#.]+", text.lower()) if w not in _STOP and len(w) > 2}


def over_ceiling(bid: float, hidden: dict, tolerance: float) -> bool:
    ceiling = hidden.get("budget_ceiling")
    return ceiling is not None and bid > ceiling * tolerance


def true_skills(persona: dict) -> set[str]:
    skills = set(persona["listed_skills"]) | set(persona["implied_skills"])
    for p in persona["projects"]:
        skills |= set(p["skills"]) | set(p["implied"])
    return {s.lower() for s in skills}


# --- heuristic mode -----------------------------------------------------------------------

def heuristic_decide(job: dict, hidden: dict, persona: dict, proposal: dict) -> dict:
    letter = proposal["cover_letter"]
    lower = letter.lower()
    must = [m["skill"] for m in hidden["must_have"]]
    covered = [s for s in must if s.lower() in lower]
    first = re.split(r"(?<=[.!?])\s|\n", letter.strip(), maxsplit=1)[0]
    specific_opening = len(_words(first) & _words(job["title"])) >= 1
    has_numbers = bool(re.search(r"\d", letter))
    known = true_skills(persona)
    mentioned = {s for s in job["required_skills"] + must if s.lower() in lower}
    unsupported = sorted(s for s in mentioned if s.lower() not in known)
    questions = job.get("screening_questions") or []
    answered = len([a for a in proposal.get("screening_answers", []) if a.strip()]) >= len(questions)

    score = 0.2
    score += 0.4 * (len(covered) / len(must) if must else 0.5)
    score += 0.15 if has_numbers else 0.0
    score += 0.15 if specific_opening else (-0.25 if hidden["dislikes_generic_opening"] else 0.0)
    score -= 0.2 * len(unsupported)
    score -= 0.0 if answered else 0.2

    if score >= 0.7:
        decision = "interview"
    elif score >= 0.45:
        decision = "reply"
    else:
        decision = "ignore"
    reasons = [f"must-haves shown: {len(covered)}/{len(must)}",
               "specific opening" if specific_opening else "generic opening",
               "concrete numbers" if has_numbers else "no concrete results",
               "screening answered" if answered else "screening questions unanswered"]
    if unsupported:
        reasons.append(f"claims not backed by profile: {', '.join(unsupported)}")
    message = None
    if decision == "reply":
        message = (f"Thanks for your proposal for \"{job['title']}\". Could you tell me more about "
                   f"how you would approach {must[0] if must else 'this'}?")
    elif decision == "interview":
        message = (f"Your proposal for \"{job['title']}\" stood out. Can we schedule a short call "
                   f"this week? Please suggest a couple of times.")
    return {"decision": decision, "reason": "; ".join(reasons), "score": round(score, 3),
            "unsupported_claims": unsupported, "message": message, "mode": "heuristic"}


def heuristic_reply(job: dict, hidden: dict, decision: dict, history: list[dict]) -> dict:
    """Client's answer to the freelancer's latest message. `history` is oldest first."""
    freelancer_turns = [m for m in history if m["sender"] == "freelancer"]
    last = freelancer_turns[-1]["body"] if freelancer_turns else ""
    score = decision.get("score", 0.5)
    if _SLOT.search(last):
        return {"decision": "interview",
                "message": "That time works for me - I've booked it. Talk soon."}
    if len(freelancer_turns) >= 3:
        if score >= 0.6:
            return {"decision": "hire", "message": "Great conversation. I'm sending you the offer now."}
        return {"decision": "lost", "message": "Thanks for your time - we've decided to go with "
                                               "another freelancer."}
    return {"decision": "continue",
            "message": "Thanks, that helps. What timeline would you propose, and when could we talk?"}


# --- dispatch -----------------------------------------------------------------------------

class SimulatedClient:
    def __init__(self, cfg: dict, store):
        self.cfg = cfg["client"]
        self.store = store

    def decide(self, job: dict, hidden: dict, client: dict, persona: dict, proposal: dict) -> dict:
        if over_ceiling(proposal["bid_amount"], hidden, self.cfg["over_ceiling_tolerance"]):
            return {"decision": "ignore", "reason": "bid above the client's budget ceiling",
                    "score": 0.0, "unsupported_claims": [], "message": None, "mode": "rule"}
        if self.cfg["mode"] == "llm":
            from gigsim.llm_client import llm_decide  # step 5
            return llm_decide(self.cfg, self.store, job, hidden, client, persona, proposal)
        return heuristic_decide(job, hidden, persona, proposal)

    def reply(self, job: dict, hidden: dict, client: dict, persona: dict, decision: dict,
              history: list[dict]) -> dict:
        if self.cfg["mode"] == "llm":
            from gigsim.llm_client import llm_reply  # step 5
            return llm_reply(self.cfg, self.store, job, hidden, client, persona, decision, history)
        return heuristic_reply(job, hidden, decision, history)
