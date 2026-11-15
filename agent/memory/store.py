"""Long-term memory on a LangGraph store (InMemoryStore in tests, PostgresStore in production).

Namespaces (per user):
  ("style_candidates", user)  pattern -> {count, examples}   observations from edits, not yet rules
  ("style", user)             pattern -> {rule, since}        promoted rules, used by Writer and Liaison
  ("outcome", user)           category -> {submitted, replied, interview, hired, lost}

Edits are turned into patterns by deterministic diff features, not by an LLM, so the user can see
exactly why a rule exists. The UI's memory viewer lists and deletes items through these functions.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from langgraph.store.base import BaseStore

from agent.memory.promotion_rules import outcome_is_recordable, promote

SENTENCE = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]{4,}")
# Words worth learning "never say X" about: generic filler that clients skim past.
FILLER = {"passionate", "dedicated", "hardworking", "expert", "experienced", "extensive", "leverage", "synergy",
          "cutting-edge", "seamless", "robust", "innovative", "excited", "delighted", "guarantee", "dear",
          "sir/madam", "highly", "skilled", "professional", "world-class", "best-in-class", "end-to-end"}

RULE_TEXT = {
    "cut_first_sentence": "Start directly with the client's problem; the user deletes generic first sentences.",
    "shortened": "Keep it shorter; the user regularly cuts drafts by a fifth or more.",
    "lengthened": "Add more detail; the user regularly expands drafts.",
    "removed_sign_off": "Do not end with a sign-off like 'Best regards'.",
}


def edit_patterns(original: str, edited: str) -> set[str]:
    """Deterministic features of one edit."""
    pats = set()
    o_sent, e_sent = SENTENCE.split(original.strip()), SENTENCE.split(edited.strip())
    if len(o_sent) > 1 and e_sent and o_sent[0].strip() not in edited and o_sent[1].strip()[:40] in edited:
        pats.add("cut_first_sentence")
    if len(edited) < 0.8 * len(original):
        pats.add("shortened")
    elif len(edited) > 1.2 * len(original):
        pats.add("lengthened")
    if re.search(r"(best regards|kind regards|thanks?,|cheers)\W*$", original.strip(), re.IGNORECASE) and not \
            re.search(r"(best regards|kind regards|thanks?,|cheers)\W*$", edited.strip(), re.IGNORECASE):
        pats.add("removed_sign_off")
    removed = {w.lower() for w in WORD.findall(original)} - {w.lower() for w in WORD.findall(edited)}
    pats |= {f"never_say:{w}" for w in removed & FILLER}
    return pats


def rule_text(pattern: str) -> str:
    if pattern.startswith("never_say:"):
        return f"Never use the word '{pattern.split(':', 1)[1]}'; the user removes it."
    return RULE_TEXT.get(pattern, pattern)


def record_edit(store: BaseStore, user_id: str, original: str, edited: str, source: str) -> list[str]:
    """Observe one edit; promote patterns that pass the rule. Returns newly promoted patterns."""
    cand_ns, style_ns = ("style_candidates", user_id), ("style", user_id)
    counts = {item.key: item.value["count"] for item in store.search(cand_ns, limit=1000)}
    promoted = []
    for p in sorted(edit_patterns(original, edited)):
        old = store.get(cand_ns, p)
        value = old.value if old else {"count": 0, "examples": []}
        value["count"] += 1
        value["examples"] = (value["examples"] + [source])[-5:]
        store.put(cand_ns, p, value)
        counts[p] = value["count"]
        if store.get(style_ns, p) is None and promote(p, counts):
            store.put(style_ns, p, {"rule": rule_text(p), "since": datetime.now(UTC).isoformat(),
                                    "evidence_edits": value["count"]})
            promoted.append(p)
    return promoted


def style_rules(store: BaseStore | None, user_id: str) -> list[str]:
    if store is None:
        return []
    return [item.value["rule"] for item in store.search(("style", user_id), limit=50)]


def forget(store: BaseStore, user_id: str, namespace: str, key: str) -> None:
    """Delete a memory item (the UI's memory viewer). Also clears its candidate count."""
    store.delete((namespace, user_id), key)
    if namespace == "style":
        store.delete(("style_candidates", user_id), key)


def record_outcome(store: BaseStore, user_id: str, category: str, status: str, submitted_by_gigbid: bool) -> bool:
    if not outcome_is_recordable(status, submitted_by_gigbid):
        return False
    ns = ("outcome", user_id)
    old = store.get(ns, category)
    value = old.value if old else {"submitted": 0, "replied": 0, "interview": 0, "hired": 0, "lost": 0}
    value["submitted"] += 1
    value[status] += 1
    store.put(ns, category, value)
    return True


def outcome_stats(store: BaseStore, user_id: str) -> dict[str, dict]:
    return {item.key: item.value for item in store.search(("outcome", user_id), limit=50)}
