"""Shared captions / hashtags for Shorts cross-posting."""

from __future__ import annotations

from typing import List, Optional

from src.content.copy_guard import looks_like_filename_slug, safe_caption
from src.content.humanize_copy import (
    pick_threads_tags,
    should_use_hashtags,
)
from src.content.naturalize import naturalize_text

APPROVED_HASHTAGS = [
    "bitcoin",
    "crypto",
    "cryptonews",
    "btc",
    "ethereum",
    "sec",
    "etf",
    "federalreserve",
    "cryptoregulation",
    "blockchain",
]

# One optional ticker tag when the story is clearly about that entity (4 core + 1 topic).
TOPIC_HASHTAGS: dict[str, str] = {
    "ripple": "ripple",
    "xrp": "ripple",
    "solana": "solana",
    " sol ": "solana",
    "binance": "binance",
    " bnb": "binance",
    "coinbase": "coinbase",
    "cardano": "cardano",
    " ada": "cardano",
}

TAG_HINTS = {
    "bitcoin": ("bitcoin", "btc", "blackrock"),
    "btc": ("bitcoin", "btc"),
    "ethereum": ("ethereum", "eth", "ether"),
    "sec": ("sec", "securities"),
    "etf": ("etf", "inflow", "blackrock", "ishares"),
    "federalreserve": ("fed", "fomc", "powell", "rates", "cpi"),
    "cryptoregulation": ("sec", "regulation", "cftc", "law"),
    "blockchain": ("blockchain", "onchain", "on-chain"),
    "crypto": ("crypto",),
    "cryptonews": ("news",),
}

DEFAULT_HASHTAGS = APPROVED_HASHTAGS[:6]
DISCLAIMER = "Not financial advice. News and education only."
IG_CTA = "Full breakdown on YouTube."
CAROUSEL_CTA = "Swipe for context."


def _seed_value(seed: str) -> int:
    text = (seed or "coinwire").strip()
    return sum(ord(c) for c in text)


def should_add_engagement_question(seed: str, rate: float = 0.25) -> bool:
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    return (_seed_value(seed) % 100) < int(rate * 100)


def pick_approved_hashtags(text: str, count: int = 5) -> List[str]:
    blob = (text or "").lower()
    scored: list[tuple[int, str]] = []
    for tag in APPROVED_HASHTAGS:
        hints = TAG_HINTS.get(tag, (tag,))
        score = sum(1 for hint in hints if hint and hint in blob)
        if tag in {"crypto", "cryptonews"}:
            score = max(score, 1)
        scored.append((score, tag))
    scored.sort(key=lambda item: (-item[0], APPROVED_HASHTAGS.index(item[1])))
    picked: list[str] = []
    for _score, tag in scored:
        if tag not in picked:
            picked.append(tag)
        if len(picked) >= count:
            break
    return picked[:count]


def _detect_topic_tag(text: str) -> Optional[str]:
    blob = f" {(text or '').lower()} "
    for hint, tag in TOPIC_HASHTAGS.items():
        if hint in blob:
            return tag
    return None


def pick_ig_hashtag_tags(text: str, count: int = 5) -> List[str]:
    """Exactly `count` tags: up to 4 from core pool + 1 topic tag when relevant."""
    topic = _detect_topic_tag(text)
    core_slots = count - (1 if topic else 0)
    core = pick_approved_hashtags(text, core_slots)
    if topic and topic not in core:
        return (core + [topic])[:count]
    return pick_approved_hashtags(text, count)[:count]


def fix_hashtag_block(body: str, article_text: str, count: int) -> str:
    tags = pick_ig_hashtag_tags(article_text, count)
    tag_line = " ".join(f"#{t}" for t in tags)
    return f"{body.rstrip()}\n\n{tag_line}".strip()


def _tag_line(text: str, count: int) -> str:
    return " ".join(f"#{t}" for t in pick_ig_hashtag_tags(text, count))


def build_caption(
    title: str,
    description: str = "",
    *,
    hashtags: Optional[List[str]] = None,
    max_len: int = 2200,
    include_disclaimer: bool = False,
    tag_count: int = 5,
    cta: str = IG_CTA,
) -> str:
    title = naturalize_text(title.strip())
    if looks_like_filename_slug(title):
        title = ""
    parts = [title]
    desc = naturalize_text((description or "").strip())
    if desc and desc.lower() != title.lower():
        first = desc.split("\n")[0].strip()
        if first and first not in (parts[0] or ""):
            parts.append(first[:280])
    if cta:
        parts.append(cta)
    if include_disclaimer:
        parts.append(DISCLAIMER)
    if hashtags:
        tag_line = " ".join(f"#{t.lstrip('#')}" for t in hashtags[:tag_count])
    else:
        tag_line = _tag_line(f"{title} {description}", tag_count)
    parts.append(tag_line)
    caption = "\n\n".join(p for p in parts if p)
    if len(caption) <= max_len:
        return caption
    return caption[: max_len - 1].rstrip() + "..."


def build_carousel_caption(
    title: str,
    description: str = "",
    *,
    source: str = "",
    max_len: int = 2200,
) -> str:
    title = naturalize_text(title.strip())
    if looks_like_filename_slug(title):
        title = ""
    desc = naturalize_text((description or "").strip())
    first = desc.split("\n")[0].strip()[:280] if desc else ""
    lines = [title]
    if first and first.lower() not in title.lower():
        lines.append(first)
    lines.append(CAROUSEL_CTA)
    if source:
        lines.append(f"Source: {source}")
    lines.append(_tag_line(f"{title} {description}", 4))
    caption = "\n\n".join(p for p in lines if p)
    return caption[:max_len]


def build_threads_text(
    title: str,
    description: str = "",
    youtube_url: str = "",
    *,
    engagement_question: str = "",
    seed: str = "",
) -> str:
    """Legacy Short-linked Threads helper. Desk no longer uses this path."""
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
    carousel_caption: str = "",
) -> list[tuple[str, str]]:
    """Hint + body pairs. Body is meant to be copied as-is (no extra lines)."""
    ig = safe_caption(ig_caption) or build_caption(title, max_len=2200)
    packs = [
        ("TikTok / IG Reel — long-press NEXT message → Copy", ig[:2200]),
    ]
    carousel = safe_caption(carousel_caption)
    if carousel:
        packs.append(
            ("IG carousel caption — long-press NEXT → Copy", carousel[:2200]),
        )
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
