"""Shared captions / hashtags for Shorts cross-posting."""

from __future__ import annotations

from typing import List, Optional

from src.content.humanize_copy import (
    pick_threads_tags,
    should_use_hashtags,
)
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


def _seed_value(seed: str) -> int:
    text = (seed or "coinwire").strip()
    return sum(ord(c) for c in text)


def should_add_engagement_question(seed: str, rate: float = 0.25) -> bool:
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    return (_seed_value(seed) % 100) < int(rate * 100)


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
        first = desc.split("\n")[0].strip()
        if first and first not in parts[0]:
            parts.append(first[:280])
    if include_disclaimer:
        parts.append(DISCLAIMER)
    parts.append(tag_line)
    caption = "\n\n".join(p for p in parts if p)
    if len(caption) <= max_len:
        return caption
    return caption[: max_len - 1].rstrip() + "..."


def build_threads_text(
    title: str,
    description: str = "",
    youtube_url: str = "",
    *,
    engagement_question: str = "",
    seed: str = "",
) -> str:
    """Threads hard limit is 500 characters. Reads like a person posted it."""
    seed = seed or title
    lines = [naturalize_text(title.strip())]
    title_norm = lines[0].lower()
    desc = naturalize_text((description or "").strip()).split("\n")[0][:140]
    if desc and desc.lower() != title_norm and desc.lower() not in title_norm:
        lines.append(desc)
    if engagement_question:
        lines.append(naturalize_text(engagement_question.strip()))
    if youtube_url:
        lines.append(youtube_url)
    if should_use_hashtags(seed):
        lines.append(pick_threads_tags(seed))
    text = "\n\n".join(line for line in lines if line)
    return text[:500]


def phone_copy_packs(
    title: str,
    *,
    youtube_url: str = "",
    ig_caption: str = "",
    threads_text: str = "",
) -> list[tuple[str, str]]:
    """Hint + body pairs. Body is meant to be copied as-is (no extra lines)."""
    ig = ig_caption.strip() or build_caption(title, max_len=400, include_disclaimer=True)
    threads = threads_text.strip() or build_threads_text(title, youtube_url=youtube_url)
    packs = [
        ("TikTok / IG — long-press NEXT message → Copy", ig[:400]),
        ("Threads — long-press NEXT message → Copy (text only, no video)", threads[:500]),
    ]
    if youtube_url:
        packs.append(
            (
                "X — optional, long-press NEXT → Copy",
                f"{title.strip()[:180]}\n{youtube_url}",
            )
        )
    return packs


def build_phone_repost_caption(
    title: str,
    *,
    youtube_url: str = "",
    ig_caption: str = "",
    threads_text: str = "",
) -> str:
    """Single-message fallback if split copy packs cannot be sent."""
    packs = phone_copy_packs(
        title,
        youtube_url=youtube_url,
        ig_caption=ig_caption,
        threads_text=threads_text,
    )
    parts = [title.strip(), youtube_url, "", "PHONE: save video → gallery → app"]
    for hint, body in packs:
        parts.extend(["", hint, body])
    return "\n".join(p for p in parts if p).strip()
