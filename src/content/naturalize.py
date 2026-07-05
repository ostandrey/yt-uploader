"""Normalize punctuation for social posts and voiceover (less AI-looking)."""

from __future__ import annotations

import re

from src.media.fonts import ascii_safe


def naturalize_text(text: str) -> str:
    """
    Replace em/en dashes and smart quotes with plain ASCII punctuation.
    Use on all user-facing generated copy (titles, captions, Telegram, Threads).
    Preserves line breaks (important for voiceover scripts).
    """
    if not text:
        return ""
    cleaned = ascii_safe(text)
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
