"""Sentence overlap checks so TG / Threads / Context do not repeat the lead."""

from __future__ import annotations

import re

_STOP = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
    "as",
    "at",
    "by",
    "from",
    "that",
    "this",
    "will",
    "its",
}
_SENT = re.compile(r"(?<=[.!?])\s+")


def _tokens(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9$]+", (text or "").lower())
        if word not in _STOP and len(word) > 1
    }


def overlap_ratio(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENT.split((text or "").strip()) if part.strip()]


def shares_lead(text: str, banned: list[str], *, threshold: float = 0.62) -> bool:
    """True if any sentence in text is a near-copy of a banned lead/bullet."""
    sentences = split_sentences(text)
    if not sentences:
        sentences = [text or ""]
    for sentence in sentences:
        for ban in banned:
            if ban and overlap_ratio(sentence, ban) >= threshold:
                return True
    return False
