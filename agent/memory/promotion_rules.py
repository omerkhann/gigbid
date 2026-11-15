"""Explicit rules for what may enter long-term memory (assignment R7, C2).

Nothing reaches long-term memory except through these functions. Raw tool output never does.

Style memory: a pattern seen in a user's edits becomes a style rule only when it has appeared in
at least STYLE_MIN_EDITS separate edits (so one-off fixes don't become rules) and its opposite has
been seen less than half as often (so contradictory habits never promote either way).

Outcome memory: only final marketplace statuses for proposals GigBid itself submitted are recorded.
"""

from __future__ import annotations

STYLE_MIN_EDITS = 3
FINAL_STATUSES = {"replied", "interview", "hired", "lost"}
OPPOSITES = {"shortened": "lengthened", "lengthened": "shortened"}


def should_promote_style_edit(edit_count: int, consistent_pattern: bool) -> bool:
    """Starter-kit signature: promote after enough consistent observations."""
    return edit_count >= STYLE_MIN_EDITS and consistent_pattern


def promote(pattern: str, counts: dict[str, int]) -> bool:
    opposite = OPPOSITES.get(pattern)
    consistent = opposite is None or 2 * counts.get(opposite, 0) < counts.get(pattern, 0)
    return should_promote_style_edit(counts.get(pattern, 0), consistent)


def outcome_is_recordable(status: str, submitted_by_gigbid: bool) -> bool:
    return submitted_by_gigbid and status in FINAL_STATUSES
