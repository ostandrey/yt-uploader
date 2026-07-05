"""Shared captions / hashtags for Shorts cross-posting."""

from __future__ import annotations

from typing import List, Optional

from src.content.naturalize import naturalize_text

DEFAULT_HASHTAGS = [
    "bitcoin",
    "crypto",
    "cryptonews",
    "ethereum",
    "coinwire",
    "marketnews",
]

DISCLAIMER = "Not financial advice. News and education only."

ENGAGEMENT_QUESTIONS = [
    "What's your take: bullish or bearish?",
    "Buying the dip or waiting on the sidelines?",
    "Does this change your outlook for the week?",
    "Would you add, hold, or reduce exposure here?",
    "What would you watch next: BTC or alts?",
]


def _seed_value(seed: str) -> int:
    text = (seed or "coinwire").strip()
    return sum(ord(c) for c in text)


def should_add_engagement_question(seed: str, rate: float = 0.35) -> bool:
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    return (_seed_value(seed) % 100) < int(rate * 100)


def pick_engagement_question(seed: str) -> str:
    return ENGAGEMENT_QUESTIONS[_seed_value(seed) % len(ENGAGEMENT_QUESTIONS)]


def build_caption(
    title: str,
    description: str = "",
    *,
    hashtags: Optional[List[str]] = None,
    max_len: int = 2200,
    include_disclaimer: bool = True,
) -> str:
    tags = hashtags or DEFAULT_HASHTAGS
    tag_line = " ".join(f"#{t.lstrip('#')}" for t in tags[:12])
    parts = [naturalize_text(title.strip())]
    desc = naturalize_text((description or "").strip())
    if desc and desc.lower() != title.strip().lower():
        # Keep caption short — first paragraph only
        first = desc.split("\n")[0].strip()
        if first and first not in parts[0]:
            parts.append(first[:280])
    if include_disclaimer:
        parts.append(DISCLAIMER)
    parts.append(tag_line)
    caption = "\n\n".join(p for p in parts if p)
    if len(caption) <= max_len:
        return caption
    return caption[: max_len - 1].rstrip() + "…"


def build_threads_text(
    title: str,
    description: str = "",
    youtube_url: str = "",
    *,
    engagement_question: str = "",
) -> str:
    """Threads hard limit is 500 characters."""
    lines = [naturalize_text(title.strip())]
    title_norm = lines[0].lower()
    desc = naturalize_text((description or "").strip()).split("\n")[0][:160]
    if desc and desc.lower() != title_norm:
        lines.append(desc)
    if engagement_question:
        lines.append(naturalize_text(engagement_question.strip()))
    if youtube_url:
        lines.append(youtube_url)
    lines.append("#bitcoin #crypto #coinwire")
    text = "\n\n".join(line for line in lines if line)
    return text[:500]
