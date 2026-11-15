"""Mask emails and phone numbers before anything is logged (assignment E4: PII masking in logs)."""

from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def _phone(m: re.Match[str]) -> str:
    return "[PHONE]" if 9 <= sum(c.isdigit() for c in m.group(0)) <= 15 else m.group(0)


def mask_text(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    parts, last = [], 0
    for url in _URL.finditer(text):  # IDs inside URLs are not phone numbers
        parts += [_PHONE.sub(_phone, text[last:url.start()]), url.group(0)]
        last = url.end()
    parts.append(_PHONE.sub(_phone, text[last:]))
    return "".join(parts)


def mask(value: Any) -> Any:
    """Mask PII anywhere inside nested dicts/lists/strings."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [mask(v) for v in value]
    return value
