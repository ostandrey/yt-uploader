"""
Diversified Threads news flash (standalone text, not a Short caption).

No engagement questions. Hashtags only for regulatory stories (one tag).
"""

from __future__ import annotations

from typing import Dict, List, Literal

from src.content.humanize_copy import bullet_to_prose
from src.content.naturalize import naturalize_text
from src.content.news_filter import extract_key_bullets

ThreadsTier = Literal["breaking", "insight", "strong", "standard"]
PulseVariant = Literal[
    "bullets",
    "prose",
    "takeaway",
    "context",
    "breaking_lead",
    "minimal",
]

MAX_LEN = 500

TIER_RANK = {"standard": 1, "strong": 2, "insight": 3, "breaking": 4}
REG_HINTS = ("sec", "cftc", "etf", "regulat", "fed ", "federal reserve", "fomc")


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
        ]
    elif tier == "insight":
        pool = ["takeaway", "prose", "context", "minimal"]
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
    style = _seed_value(seed + ":brk") % 3
    if style == 0:
        return f"Breaking: {title}"
    if style == 1:
        return title
    return f"Just in: {title}"


def _is_regulatory(article: Dict) -> bool:
    blob = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return any(hint in blob for hint in REG_HINTS)


def _regulatory_tag(article: Dict) -> str:
    blob = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    if "sec" in blob or "cftc" in blob or "regulat" in blob:
        return "#sec"
    if "bitcoin" in blob or "btc" in blob:
        return "#bitcoin"
    return "#crypto"


def build_threads_news_pulse(
    article: Dict,
    *,
    tier: str = "strong",
    seed: str = "",
    question_rate: float = 0.0,
) -> tuple[str, PulseVariant]:
    """
    Build a plain-text Threads news flash (no video, no YouTube CTA).
    question_rate is ignored — questions are a separate editorial type.
    """
    del question_rate
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

    elif variant == "minimal":
        lines.append(title)
        if tier == "insight" and bullets:
            lines.append(bullet_to_prose(bullets[0])[:140])

    else:
        lines.append(title)

    body = "\n\n".join(line for line in lines if line)
    if _is_regulatory(article):
        tag = _regulatory_tag(article)
        if tag:
            body = f"{body}\n\n{tag}"
    return _clip(body), variant
