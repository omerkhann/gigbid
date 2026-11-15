"""Content rules from the active policy file. GigSim keeps its own copy of the contact
detector (rather than importing GigBid's code) so the frozen simulator has no dependencies
on the system it grades."""

from __future__ import annotations

import math
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def has_contact_details(text: str) -> bool:
    if _EMAIL.search(text):
        return True
    without_urls = _URL.sub(" ", text)
    return any(9 <= sum(c.isdigit() for c in m.group(0)) <= 15 for m in _PHONE.finditer(without_urls))


def violations(policy: dict, text: str) -> list[dict]:
    found = []
    lower = text.lower()
    for rule in policy.get("content_rules", []):
        if rule["detector"] == "contact_details":
            hit = has_contact_details(text)
        elif rule["detector"] == "keywords":
            hit = any(k in lower for k in rule["keywords"])
        else:
            hit = False
        if hit:
            found.append({"rule_id": rule["id"], "description": rule["description"]})
    return found


def connects_cost(policy: dict, job: dict) -> int:
    return math.ceil(job["connects_cost"] * policy["connects"]["cost_multiplier"])
