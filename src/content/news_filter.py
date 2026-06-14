"""
Serious-news scoring and Telegram summary builder for Coin Wire.
Rule-based — no LLM, runs fully automated.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# High-impact signals (weight)
HIGH_IMPACT_KEYWORDS: Dict[str, int] = {
    "etf": 10,
    "sec": 10,
    "fed": 9,
    "federal reserve": 9,
    "regulation": 8,
    "regulatory": 8,
    "blackrock": 8,
    "fidelity": 7,
    "treasury": 8,
    "institutional": 7,
    "wall street": 7,
    "bitcoin": 5,
    "ethereum": 5,
    "inflation": 6,
    "interest rate": 7,
    "rate cut": 7,
    "rate hike": 7,
    "lawsuit": 7,
    "settlement": 6,
    "approval": 7,
    "approved": 7,
    "ban": 7,
    "banned": 7,
    "hack": 8,
    "exploit": 8,
    "billion": 8,
    "million": 5,
    "outflow": 7,
    "inflow": 7,
    "tokenization": 7,
    "defi": 5,
    "stablecoin": 6,
    "binance": 6,
    "coinbase": 6,
    "microstrategy": 6,
}

FLUFF_PATTERNS = [
    "could hit",
    "could reach",
    "might hit",
    "might reach",
    "price prediction",
    "price target",
    "analyst predicts",
    "analyst says price",
    "memecoin",
    "meme coin",
    "celebrity",
    "influencer",
    "airdrop",
    "top 5",
    "top 10",
    "top five",
    "best coins",
    "coins to buy",
    "coins to watch",
    "weekly roundup",
    "daily roundup",
    "week in review",
    "today in crypto",
    "what happened in crypto",
    "here's what",
    "here is what",
    "opinion:",
    "sponsored",
]

GENERIC_TITLE_PATTERNS = FLUFF_PATTERNS  # shared

SOURCE_BONUS: Dict[str, int] = {
    "the_block": 6,
    "coindesk": 5,
    "decrypt": 3,
    "cointelegraph": 2,
}

EXCLUDE_KEYWORDS = [
    "buy now", "sell now", "100x", "pump", "signal", "airdrop scam",
    "guaranteed returns", "not financial advice but",
]

HASHTAG_MAP: List[Tuple[str, str]] = [
    ("bitcoin", "#Bitcoin"),
    ("btc", "#Bitcoin"),
    ("ethereum", "#Ethereum"),
    ("eth", "#Ethereum"),
    ("etf", "#ETF"),
    ("sec", "#SEC"),
    ("fed", "#Fed"),
    ("federal reserve", "#Fed"),
    ("defi", "#DeFi"),
    ("stablecoin", "#Stablecoin"),
    ("regulation", "#Regulation"),
    ("wall street", "#WallStreet"),
    ("tokenization", "#Tokenization"),
    ("blackrock", "#BlackRock"),
    ("inflation", "#Macro"),
    ("interest rate", "#Rates"),
    ("hack", "#Security"),
    ("exploit", "#Security"),
]

FACT_SIGNAL_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*%|\$\s*[\d,.]+\s*(?:million|billion|m|b)?|"
    r"etf|sec|fed|billion|million|outflow|inflow|approval|lawsuit|"
    r"rate cut|rate hike|blackrock|treasury)",
    re.IGNORECASE,
)


def _article_text(article: Dict) -> str:
    return f"{article.get('title', '')} {article.get('summary', '')}".lower()


def is_fluff(article: Dict) -> bool:
    text = _article_text(article)
    return any(pattern in text for pattern in FLUFF_PATTERNS)


def is_generic_roundup(title: str) -> bool:
    lower = title.lower()
    return any(pattern in lower for pattern in GENERIC_TITLE_PATTERNS)


def article_age_hours(article: Dict) -> Optional[float]:
    published = article.get("published")
    if not published:
        return None
    try:
        pub_date = datetime(*published[:6])
        delta = datetime.now() - pub_date
        return delta.total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def score_article(
    article: Dict,
    min_short_score: int = 12,
) -> int:
    """Higher = more newsworthy. Auto-picks best without human review."""
    text = _article_text(article)
    score = 0

    for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
        if keyword in text:
            score += weight

    source = article.get("source", "")
    score += SOURCE_BONUS.get(source, 0)

    for bad in EXCLUDE_KEYWORDS:
        if bad in text:
            score -= 15

    if is_fluff(article):
        score -= 20

    if is_generic_roundup(article.get("title", "")):
        score -= 15

    age_h = article_age_hours(article)
    if age_h is not None:
        if age_h <= 6:
            score += 8
        elif age_h <= 12:
            score += 5
        elif age_h <= 24:
            score += 2
        elif age_h > 48:
            score -= 10

    # Must have at least one hard news signal for shorts
    hard_signals = sum(1 for kw in ("etf", "sec", "fed", "billion", "regulation", "hack", "approval", "outflow", "inflow", "tokenization", "wall street") if kw in text)
    if hard_signals == 0 and score < min_short_score:
        score -= 5

    return score


def passes_short_filter(article: Dict, min_score: int = 12, max_age_hours: int = 24) -> bool:
    if is_fluff(article) or is_generic_roundup(article.get("title", "")):
        return False
    age_h = article_age_hours(article)
    if age_h is not None and age_h > max_age_hours:
        return False
    return score_article(article, min_short_score=min_score) >= min_score


def passes_telegram_filter(article: Dict, min_score: int = 6, max_age_hours: int = 48) -> bool:
    if is_fluff(article):
        return False
    age_h = article_age_hours(article)
    if age_h is not None and age_h > max_age_hours:
        return False
    return score_article(article) >= min_score


def extract_key_bullets(article: Dict, max_bullets: int = 3) -> List[str]:
    """Pull the most factual sentences — not just the RSS blurb."""
    title = article.get("title", "").strip()
    summary = article.get("summary", "").strip()
    candidates: List[Tuple[int, str]] = []

    if title:
        candidates.append((score_sentence(title) + 3, title))

    for sentence in re.split(r"(?<=[.!?])\s+", summary):
        sentence = sentence.strip()
        if len(sentence) < 30:
            continue
        candidates.append((score_sentence(sentence), sentence))

    candidates.sort(key=lambda item: item[0], reverse=True)
    bullets: List[str] = []
    seen: set[str] = set()

    for _, sentence in candidates:
        key = sentence[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        clean = sentence.rstrip(".")
        if len(clean) > 160:
            clean = clean[:157].rsplit(" ", 1)[0] + "..."
        bullets.append(clean)
        if len(bullets) >= max_bullets:
            break

    if not bullets and summary:
        bullets.append(summary[:200].rsplit(" ", 1)[0] + ("..." if len(summary) > 200 else ""))

    return bullets


def score_sentence(sentence: str) -> int:
    score = 0
    lower = sentence.lower()
    if FACT_SIGNAL_RE.search(sentence):
        score += 6
    for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
        if keyword in lower:
            score += min(weight, 4)
    if re.search(r"\d", sentence):
        score += 2
    return score


def build_hashtags(article: Dict, max_tags: int = 5) -> str:
    text = _article_text(article)
    tags: List[str] = []
    for keyword, tag in HASHTAG_MAP:
        if keyword in text and tag not in tags:
            tags.append(tag)
        if len(tags) >= max_tags - 1:
            break
    tags.append("#CoinWire")
    return " ".join(tags[:max_tags])


def format_telegram_post(article: Dict) -> str:
    """Rich post: headline + key bullets + hashtags + link."""
    bullets = extract_key_bullets(article, max_bullets=3)
    hashtags = build_hashtags(article)
    source_label = article.get("source", "news").replace("_", " ").title()

    lines = [f"📰 {article['title']}", ""]
    for bullet in bullets:
        lines.append(f"• {bullet}")
    lines.extend([
        "",
        hashtags,
        "",
        f"🔗 {article['link']}",
        f"📌 {source_label}",
        "",
        "Not financial advice. News and education only.",
    ])
    return "\n".join(lines)
