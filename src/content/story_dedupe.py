"""Near-duplicate story fingerprints for posting dedup."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

_STOP = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "its",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "after",
    "says",
    "said",
    "report",
    "reports",
    "update",
    "move",
    "over",
}


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
    return token


def normalize_title(title: str) -> str:
    text = (title or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [_stem(t) for t in text.split() if t and t not in _STOP]
    return " ".join(t for t in tokens if t)


def story_fingerprint(title: str, link: str = "") -> str:
    """Stable id for 'same story' across sources / tiny title edits."""
    norm = normalize_title(title)
    if len(norm) < 12 and link:
        clean = re.sub(r"[?#].*$", "", (link or "").strip().lower())
        norm = f"{norm} {clean}".strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def titles_similar(a: str, b: str, *, threshold: float = 0.78) -> bool:
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if len(ta) >= 3 and len(tb) >= 3:
        shared = ta & tb
        if len(shared) >= 4:
            return True
        overlap = len(shared) / max(len(ta | tb), 1)
        if overlap >= 0.55:
            return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold
