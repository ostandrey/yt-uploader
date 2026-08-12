"""Never show a render filename slug as a social caption or title."""

from __future__ import annotations

import re

SLUG_RE = re.compile(r"^short[_\s-]\d{8}[_\s-]\d{4}", re.IGNORECASE)


def looks_like_filename_slug(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(SLUG_RE.match(raw.replace(" ", "_")))


def safe_caption(*candidates: str) -> str:
    """First non-empty value that is not a short_YYYYMMDD_HHMM slug."""
    for raw in candidates:
        text = (raw or "").strip()
        if text and not looks_like_filename_slug(text):
            return text
    return ""


def display_title(title: str, fallback: str = "Short готовий") -> str:
    text = (title or "").strip()
    if not text or looks_like_filename_slug(text):
        return fallback
    return text
