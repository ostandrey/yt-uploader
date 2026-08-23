"""
Diversified Threads news flash (standalone text, not a Short caption).

No engagement questions. Hashtags only for regulatory stories (one tag).
Must not reuse Telegram headline/bullet wording — but MUST still state a fact.
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
MIN_FACT_WORDS = 8

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
_PHILOSOPHY = {
    "the headline is not the filing",
    "the next official document is the thing to wait for",
    "wait for the primary document",
    "treat the headline as a calendar marker",
    "the calendar mark is the story",
    "the docket matters more than the headline",
    "is the name on the docket",
}


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


def _finish(line: str) -> str:
    line = naturalize_text(line or "").strip()
    if not line:
        return ""
    if not line.endswith((".", "?", "!")):
        line += "."
    return line


def _concrete_fact(title: str, summary: str, bullets: List[str]) -> str:
    """One readable fact the reader can understand without the original article."""
    candidates: List[str] = []
    for sent in split_sentences(summary):
        candidates.append(sent)
    if title:
        candidates.append(title)
    candidates.extend(bullets)
    for raw in candidates:
        line = _finish(raw)
        words = line.split()
        if len(words) < MIN_FACT_WORDS:
            continue
        # Skip pure philosophy if it somehow appears in source.
        low = line.lower()
        if any(p in low for p in _PHILOSOPHY):
            continue
        if len(words) > 28:
            line = _finish(" ".join(words[:28]))
        return line
    # Last resort: title even if short — still better than empty philosophy.
    if title and len(title.split()) >= 4:
        return _finish(title)
    return ""


def _angle_color(title: str, summary: str, fact: str) -> str:
    """Optional second line — never ships alone without a fact."""
    blob = f"{title}. {summary}"
    dated = _DATE.search(blob)
    if dated:
        return _finish(f"{dated.group(0).strip()} is on the calendar — wait for the primary print")
    money = _MONEY.search(blob)
    if money:
        return _finish(f"{money.group(0).strip()} is the figure in the story, not a forecast")
    agency = _AGENCY.search(blob)
    if agency and fact:
        name = agency.group(0)
        if name.lower() in {"the fed", "fed"}:
            name = "Fed"
        return _finish(f"{name} is named — treat the headline as a marker until the document is public")
    return ""


def _distinct_line(candidates: List[str], banned: list[str]) -> str:
    for raw in candidates:
        line = _finish(raw)
        if len(line.split()) < MIN_FACT_WORDS:
            continue
        if any(p in line.lower() for p in _PHILOSOPHY):
            continue
        if not shares_lead(line, banned):
            return line
    return ""


def _body_line(title: str, summary: str, bullets: List[str], banned: list[str], fact: str) -> str:
    leftover = split_sentences(summary)
    if leftover:
        leftover = leftover[1:] + leftover[:1]
    extras = [*leftover, *[b for b in bullets]]
    line = _distinct_line(extras, banned + [title, fact])
    if line and line.lower() != fact.lower():
        return line
    return _angle_color(title, summary, fact)


def _has_substance(text: str, fact: str) -> bool:
    if not fact or len(fact.split()) < 4:
        return False
    body = text.lower()
    # Must include some non-philosophy content from the fact.
    fact_tokens = [w for w in re.findall(r"[a-z0-9]+", fact.lower()) if len(w) > 3]
    if not fact_tokens:
        return False
    hits = sum(1 for w in fact_tokens[:8] if w in body)
    return hits >= min(3, len(fact_tokens))


def build_threads_news_pulse(
    article: Dict,
    *,
    tier: str = "strong",
    seed: str = "",
    question_rate: float = 0.0,
) -> tuple[str, PulseVariant]:
    """
    Build a plain-text Threads news flash (no video, no YouTube CTA).
    Always leads with a concrete story fact — never philosophy-only.
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
    fact = _concrete_fact(title, summary, bullets)
    if not fact:
        return "", variant

    body = _body_line(title, summary, bullets, banned, fact)
    color = _angle_color(title, summary, fact)
    takeaway = build_market_takeaway(article)

    lines: List[str] = []

    if variant == "breaking_lead":
        lines.append(fact)
        lines.append(body or color)
    elif variant == "prose":
        lines.append(fact)
        if body and body.lower() != fact.lower():
            lines.append(body)
        elif color:
            lines.append(color)
    elif variant == "takeaway":
        lines.append(fact)
        extra = takeaway if takeaway and not shares_lead(takeaway, banned) else (body or color)
        if extra and extra.lower() != fact.lower():
            lines.append(extra)
    elif variant == "context":
        lines.append(fact)
        lines.append(body or color)
    elif variant == "minimal":
        lines.append(fact)
        if color:
            lines.append(color)
    else:
        lines.append(fact)
        if body and body.lower() != fact.lower():
            lines.append(body)

    # Drop empties / dupes while keeping order.
    seen: set[str] = set()
    clean: List[str] = []
    for line in lines:
        key = (line or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(line.strip())

    text = "\n\n".join(clean)
    if shares_lead(text, banned) or not _has_substance(text, fact):
        # Soft rewrite: keep the fact, add one cautious color line if regulatory.
        text = fact
        if color and color.lower() != fact.lower():
            text = f"{fact}\n\n{color}"

    if not _has_substance(text, fact):
        return "", variant

    if _is_regulatory(article):
        tag = _regulatory_tag(article)
        if tag:
            text = f"{text}\n\n{tag}"
    return _clip(text), variant
