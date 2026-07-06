"""Make generated social copy sound like a human editor, not a template bot."""

from __future__ import annotations

import re
from typing import List

# Phrases that read as generic AI / newsletter boilerplate
AI_FILLER_PATTERNS = (
    r"\boften move\b",
    r"\btend to drag\b",
    r"\bThis is a developing story\b",
    r"\bAlways verify\b",
    r"\bNot financial advice\b",
    r"\bIn today's\b",
    r"\bIt's worth noting\b",
    r"\bHere's what you need to know\b",
    r"\bWhat this means for\b",
    r"\bremains to be seen\b",
    r"\bat the end of the day\b",
    r"\blandscape\b",
    r"\bnavigate\b",
    r"\bunderscores\b",
    r"\bhighlight(s)? the importance\b",
)

TAG_POOL = (
    "bitcoin",
    "crypto",
    "cryptonews",
    "ethereum",
    "btc",
    "markets",
    "coinwire",
    "fed",
    "etf",
)


def _seed_value(seed: str) -> int:
    return sum(ord(c) for c in (seed or "coinwire"))


def strip_ai_filler(text: str) -> str:
    out = text.strip()
    for pattern in AI_FILLER_PATTERNS:
        out = re.sub(pattern, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip(" .")
    return out


def humanize_takeaway(takeaway: str, *, max_len: int = 150) -> str:
    """Keep one short, direct sentence; drop boilerplate."""
    text = strip_ai_filler(takeaway)
    if not text:
        return ""
    first = text.split(".")[0].strip()
    if not first:
        return ""
    if not first.endswith("."):
        first += "."
    if len(first) > max_len:
        first = first[: max_len - 1].rsplit(" ", 1)[0] + "."
    return first


def bullet_to_prose(bullet: str) -> str:
    """Turn a bullet line into a normal sentence when we skip dash lists."""
    text = bullet.strip().rstrip(".")
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]
    if not text.endswith((".", "!", "?")):
        text += "."
    return text


def pick_threads_tags(seed: str, *, count: int = 2) -> str:
    """2 tags, not the same block every post."""
    start = _seed_value(seed) % len(TAG_POOL)
    tags: List[str] = []
    for i in range(len(TAG_POOL)):
        tag = TAG_POOL[(start + i) % len(TAG_POOL)]
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= count:
            break
    # coinwire on ~half of posts only
    if "coinwire" in tags and (_seed_value(seed + ":cw") % 2):
        tags = [t for t in tags if t != "coinwire"]
        tags.append(TAG_POOL[_seed_value(seed + ":alt") % len(TAG_POOL)])
        tags = list(dict.fromkeys(tags))[:count]
    return " ".join(f"#{t}" for t in tags[:count])


def should_use_hashtags(seed: str, rate: float = 0.85) -> bool:
    return (_seed_value(seed + ":tags") % 100) < int(rate * 100)


def pick_engagement_question(seed: str) -> str:
    """Short, casual questions — not survey-style AI prompts."""
    questions = (
        "Bullish or bearish on this one?",
        "Would you add here or wait?",
        "Does this move your bias at all?",
        "BTC leading again or just noise?",
        "Surprised, or priced in already?",
        "Watching ETFs or spot here?",
        "Too early to call a trend?",
        "Alts follow, or lag again?",
    )
    return questions[_seed_value(seed) % len(questions)]
