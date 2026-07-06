"""
Diversified Threads "news pulse" text (not a copy of Telegram HTML).

Several layout variants rotate by article hash so the feed does not look templated.
"""

from __future__ import annotations

from typing import Dict, List, Literal

from src.content.humanize_copy import (
    bullet_to_prose,
    pick_engagement_question,
    pick_threads_tags,
    should_use_hashtags,
)
from src.content.naturalize import naturalize_text
from src.content.news_filter import extract_key_bullets
from src.publishers.captions import should_add_engagement_question

ThreadsTier = Literal["breaking", "insight", "strong", "standard"]
PulseVariant = Literal[
    "bullets",
    "prose",
    "takeaway",
    "context",
    "question_lead",
    "breaking_lead",
    "minimal",
]

MAX_LEN = 500

TIER_RANK = {"standard": 1, "strong": 2, "insight": 3, "breaking": 4}


def tier_meets_minimum(tier: str, minimum: str) -> bool:
    return TIER_RANK.get(tier, 0) >= TIER_RANK.get(minimum, 2)


def _seed_value(seed: str) -> int:
    return sum(ord(c) for c in (seed or "coinwire"))


def pick_pulse_variant(tier: str, seed: str) -> PulseVariant:
    """Deterministic variant per article — same story always gets same layout."""
    if tier == "breaking":
        pool: List[PulseVariant] = [
            "breaking_lead",
            "prose",
            "context",
            "takeaway",
            "question_lead",
        ]
    elif tier == "insight":
        pool = ["takeaway", "prose", "context", "question_lead", "minimal"]
    elif tier == "strong":
        pool = ["prose", "context", "bullets", "takeaway", "minimal"]
    else:
        pool = ["context", "minimal", "prose"]
    return pool[_seed_value(seed) % len(pool)]


def _clip(text: str, max_len: int = MAX_LEN) -> str:
    text = naturalize_text(text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:- ") + "..."


def _breaking_opener(seed: str, title: str) -> str:
    """Not every breaking post screams BREAKING — reads more human."""
    style = _seed_value(seed + ":brk") % 3
    if style == 0:
        return f"Breaking: {title}"
    if style == 1:
        return title
    return f"Just in: {title}"


def build_threads_news_pulse(
    article: Dict,
    *,
    tier: str = "strong",
    seed: str = "",
    question_rate: float = 0.25,
) -> tuple[str, PulseVariant]:
    """
    Build a plain-text Threads news post (no link, no HTML).
    Returns (text, variant_name).
    """
    seed = seed or article.get("hash") or article.get("title", "")
    title = naturalize_text(article.get("title", ""))
    summary = naturalize_text(article.get("summary", ""))
    variant = pick_pulse_variant(tier, seed)
    bullets = extract_key_bullets(article, max_bullets=2)
    first_line = summary.split(".")[0].strip()
    if first_line and not first_line.endswith("."):
        first_line += "."

    lines: List[str] = []

    if variant == "breaking_lead":
        lines.append(_breaking_opener(seed, title))
        if bullets:
            lines.append(bullet_to_prose(bullets[0]))
        elif first_line:
            lines.append(first_line)

    elif variant == "bullets":
        lines.append(title)
        for bullet in bullets[:2]:
            lines.append(f"- {bullet}")

    elif variant == "prose":
        lines.append(title)
        if bullets:
            lines.append(bullet_to_prose(bullets[0]))
            if len(bullets) > 1 and _seed_value(seed + ":p2") % 2:
                lines.append(bullet_to_prose(bullets[1]))
        elif first_line and first_line.lower() not in title.lower():
            lines.append(first_line)

    elif variant == "takeaway":
        lines.append(title)
        if bullets:
            lines.append(bullet_to_prose(bullets[0]))
        elif first_line and first_line.lower() not in title.lower():
            lines.append(first_line)

    elif variant == "context":
        lines.append(title)
        if first_line and first_line.lower() not in title.lower():
            lines.append(first_line)
        elif bullets:
            lines.append(bullet_to_prose(bullets[0]))

    elif variant == "question_lead":
        lines.append(title)
        if bullets:
            lines.append(bullet_to_prose(bullets[0]))
        if should_add_engagement_question(seed, question_rate):
            lines.append(pick_engagement_question(seed))

    elif variant == "minimal":
        lines.append(title)
        if tier == "insight" and bullets:
            lines.append(bullet_to_prose(bullets[0])[:140])

    else:
        lines.append(title)

    # Trailing question on fewer posts (not stacked with question_lead)
    if (
        variant not in ("question_lead", "minimal")
        and tier in ("breaking", "strong")
        and should_add_engagement_question(seed + ":q", question_rate * 0.5)
    ):
        lines.append(pick_engagement_question(seed + ":q"))

    body = "\n\n".join(line for line in lines if line)
    if should_use_hashtags(seed, rate=0.8):
        tags = pick_threads_tags(seed)
        body = f"{body}\n\n{tags}"
    return _clip(body), variant
