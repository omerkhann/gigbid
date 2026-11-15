"""V4 (ranking group): outcome-aware ranking.

Why: two past proposals can describe the same project in similar words, but one won and one was
ignored. What worked is better evidence (and better phrasing to imitate) than what didn't. After
retrieval, multiply each item's fused score by a factor from its outcome; non-proposal evidence is
unchanged.
"""

from __future__ import annotations

BOOST = {"won": 1.3, "replied": 1.15, "ignored": 0.8}


def outcome_factor(outcome: str | None) -> float:
    return BOOST.get(outcome or "", 1.0)
