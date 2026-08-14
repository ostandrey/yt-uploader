"""
Diversified Threads news flash (standalone text, not a Short caption).

No engagement questions. Hashtags only for regulatory stories (one tag).
Must not reuse Telegram headline/bullet wording.
"""

from __future__ import annotations

import re
from typing import Dict, List, Literal

from src.content.copy_overlap import shares_lead, split_sentences
from src.content.naturalize import naturalize_text
from src.content.news_filter import build_market_takeaway, extract_key_bullets

ThreadsTier = Literal["breaking", "insight", "strong", "standard"]
PulseVariant = Literal[
    "prose",
    "takeaway",
    "context",
    "breaking_lead",
    "minimal",
]

MAX_LEN = 500

TIER_RANK = {"standard": 1, "strong": 2, "insight": 3, "breaking": 4}
REG_HINTS = ("sec", "cftc", "etf", "regulat", "fed ", "federal reserve", "fomc")
_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,\s*\d{4})?\b",
    re.I,
)
_AGENCY = re.compile(
    r"\b(Federal Reserve|the Fed|CFTC|FOMC|OCC|FDIC|ESMA|FCA|Treasury|SEC|Fed)\b"
)
_MONEY = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:billion|million|[BMKTbmkt])?"
    r"|\d+(?:\.\d+)?\s?%",
    re.I,
)


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
        pool = ["prose", "context", "takeaway", "minimal"]
    else:
        pool = ["context", "minimal", "prose"]
    return pool[_seed_value(seed) % len(pool)]


def _clip(text: str, max_len: int = MAX_LEN) -> str:
    text = naturalize_text(text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:- ") + "..."


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


def _tg_banned(article: Dict, title: str, bullets: List[str], first_line: str) -> list[str]:
    banned = [title, first_line, *bullets]
    return [item for item in banned if item and len(item) > 12]


def _angle_opener(title: str, summary: str) -> str:
    """Lead with date / print / name — not the Telegram headline."""
    blob = f"{title}. {summary}"
    dated = _DATE.search(blob)
    if dated:
        return f"{dated.group(0).strip()} is the date to watch, not today's headline."
    money = _MONEY.search(blob)
    if money:
        return f"{money.group(0).strip()} is the print. It is not a forecast."
    agency = _AGENCY.search(blob)
    if agency:
        name = agency.group(0)
        if name.lower() in {"the fed", "fed"}:
            name = "Fed"
        return f"{name} is the name on the docket. The headline is not the filing."
    return ""


def _distinct_line(candidates: List[str], banned: list[str]) -> str:
    for raw in candidates:
        line = naturalize_text(raw or "").strip()
        if len(line) < 24:
            continue
        if not line.endswith("."):
            line += "."
        if not shares_lead(line, banned):
            return line
    return ""


def _body_line(title: str, summary: str, bullets: List[str], banned: list[str]) -> str:
    leftover = split_sentences(summary)
    if leftover:
        leftover = leftover[1:] + leftover[:1]
    extras = [
        *leftover,
        *[b for b in bullets],
        "The next official document is the thing to wait for.",
        "Treat the headline as a calendar marker until the docket is public.",
    ]
    line = _distinct_line(extras, banned + [title])
    if line:
        return line
    return "Wait for the primary document before calling a shift in the tape."


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
    first_line = split_sentences(summary)[0] if split_sentences(summary) else ""
    if first_line and not first_line.endswith("."):
        first_line += "."
    banned = _tg_banned(article, title, bullets, first_line)
    opener = _angle_opener(title, summary)
    body = _body_line(title, summary, bullets, banned)
    takeaway = build_market_takeaway(article)

    lines: List[str] = []

    if variant == "breaking_lead":
        lines.append(opener or "Just in: the docket matters more than the headline.")
        lines.append(body)
    elif variant == "prose":
        lines.append(opener or body)
        if opener:
            lines.append(body)
    elif variant == "takeaway":
        lines.append(opener or title)
        extra = takeaway if takeaway and not shares_lead(takeaway, banned) else body
        lines.append(extra)
    elif variant == "context":
        lines.append(opener or "The calendar mark is the story, not the headline.")
        lines.append(body)
    elif variant == "minimal":
        lines.append(opener or body)
    else:
        lines.append(opener or body)

    text = "\n\n".join(line for line in lines if line)
    if shares_lead(text, banned):
        text = "\n\n".join(
            line for line in (opener, "Wait for the primary document, not the headline.") if line
        )
    if _is_regulatory(article):
        tag = _regulatory_tag(article)
        if tag:
            text = f"{text}\n\n{tag}"
    return _clip(text), variant
