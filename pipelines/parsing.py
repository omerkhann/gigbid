"""Pure parsing helpers for cleaning the Kaggle datasets.

No pandas here on purpose: these functions hold the cleaning rules, and keeping
them plain Python means they can be unit-tested in CI without the data extras.
"""

from __future__ import annotations

import hashlib
import html
import math
import re

_MONEY = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Candidate phone: optional +, then digits with spaces/dots/dashes/brackets.
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_RELATIVE_TIME = re.compile(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", re.IGNORECASE)
_HOURS_PER_UNIT = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def parse_money(value: object) -> float | None:
    """'$2,500 ' -> 2500.0; '0', '', None, NaN -> None.

    In the 60k dataset a literal '0' in Start_rate means "no rate given",
    not "free", so zero is treated as missing.
    """
    if _missing(value):
        return None
    match = _MONEY.search(str(value))
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    return amount if amount > 0 else None


def parse_money_range(value: object) -> tuple[float | None, float | None]:
    """'$15.00-$30.00' -> (15.0, 30.0). A single value gives (v, v)."""
    if _missing(value):
        return (None, None)
    parts = [parse_money(p) for p in str(value).split("-")]
    parts = [p for p in parts if p is not None]
    if not parts:
        return (None, None)
    return (min(parts), max(parts))


def parse_hours_ago(value: object) -> float | None:
    """'3 days ago' -> 72.0. Used only to order jobs; GigSim sets its own clock."""
    if not isinstance(value, str):
        return None
    if "just now" in value.lower():
        return 0.0
    match = _RELATIVE_TIME.search(value)
    if not match:
        return None
    return int(match.group(1)) * _HOURS_PER_UNIT[match.group(2).lower()]


def parse_duration(value: object) -> tuple[str | None, str | None]:
    """'1 to 3 months, Less than 30 hrs/week' -> ('1 to 3 months', 'Less than 30 hrs/week')."""
    if not isinstance(value, str) or not value.strip():
        return (None, None)
    duration, _, workload = value.partition(",")
    return (duration.strip() or None, workload.strip() or None)


def _mask_phone(match: re.Match[str]) -> str:
    # Require 9-15 digits so we don't mask things like "1000 - 2000 words".
    digits = sum(ch.isdigit() for ch in match.group(0))
    return "[PHONE]" if 9 <= digits <= 15 else match.group(0)


def mask_pii(text: str) -> str:
    """Replace emails and phone numbers in real job posts with placeholders.

    These are real clients' contact details. Off-platform-contact scams are
    planted synthetically later, so we lose nothing by masking them here.
    """
    text = _EMAIL.sub("[EMAIL]", text)
    # Mask phones only outside URLs: arXiv/app-store IDs inside links look like phones.
    parts, last = [], 0
    for url in _URL.finditer(text):
        parts.append(_PHONE_CANDIDATE.sub(_mask_phone, text[last:url.start()]))
        parts.append(url.group(0))
        last = url.end()
    parts.append(_PHONE_CANDIDATE.sub(_mask_phone, text[last:]))
    return "".join(parts)


def clean_text(text: object) -> str:
    """Unescape HTML entities, normalise whitespace, mask PII."""
    if not isinstance(text, str):
        return ""
    text = html.unescape(text).replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return mask_pii(text.strip())


def normalise_for_dedup(text: str) -> str:
    """Lowercase and strip non-alphanumerics, so trivial edits don't hide a repost."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def stable_id(prefix: str, key: str) -> str:
    """Deterministic ID from a source key (e.g. the job URL), so reruns give the same IDs."""
    return f"{prefix}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"
