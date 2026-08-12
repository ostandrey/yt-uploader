"""Normalize punctuation for social posts and voiceover (less AI-looking)."""

from __future__ import annotations

import re

from src.media.fonts import ascii_safe

# Unicode dashes / minus signs that models love to emit
_DASH_CHARS = (
    "\u2014",  # em —
    "\u2013",  # en –
    "\u2012",  # figure dash
    "\u2015",  # horizontal bar
    "\u2212",  # minus
    "\ufe58",  # small em dash
    "\uff0d",  # fullwidth hyphen-minus
)


def naturalize_text(text: str) -> str:
    """
    Replace em/en dashes and smart quotes with plain ASCII punctuation.
    Use on all user-facing generated copy (titles, captions, Telegram, Threads).
    Preserves line breaks (important for voiceover scripts).
    """
    if not text:
        return ""
    cleaned = ascii_safe(text)
    for ch in _DASH_CHARS:
        cleaned = cleaned.replace(ch, "-")
    # Models often emit -- as a fake em dash
    cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
