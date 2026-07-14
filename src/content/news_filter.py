"""
Serious-news scoring and Telegram summary builder for Coin Wire.
Rule-based — no LLM, runs fully automated.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional, Tuple

from src.content.naturalize import naturalize_text

TelegramTier = Literal["breaking", "insight", "strong", "standard", "skip"]

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
    r"\betf\b|\bsec\b|\bfed\b|\bbillion\b|\bmillion\b|\boutflow\b|\binflow\b|"
    r"\bapproval\b|\blawsuit\b|rate cut|rate hike|\bblackrock\b|\btreasury\b)",
    re.IGNORECASE,
)

CRYPTO_RELEVANCE_TERMS = (
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "blockchain", "defi", "stablecoin", "binance", "coinbase",
    "solana", "xrp", "ripple", "dogecoin", "altcoin", "web3",
    "tokenization", "nft", "microstrategy", "grayscale",
    "digital asset", "on-chain", "onchain", "spot bitcoin", "spot ether",
    "coinbase", "tether", "usdc", "usdt",
)

MACRO_RELEVANCE_TERMS = (
    "federal reserve", "interest rate", "rate cut", "rate hike",
    "cpi", "inflation", "jobs report", "treasury",
)

OFF_TOPIC_TERMS = (
    "openai", "chatgpt", "xai", "artificial intelligence",
    "elon musk", "spacex", "tesla", "nvidia", "apple", "google",
    "trade secret", "copyright", "trademark",
)

_WORD_BOUNDARY_KEYWORDS = frozenset({
    "sec", "fed", "eth", "btc", "etf", "defi", "ban", "banned",
})


def _contains_term(text: str, term: str) -> bool:
    lower = text.lower()
    if term in _WORD_BOUNDARY_KEYWORDS or len(term) <= 3:
        return bool(re.search(rf"\b{re.escape(term)}\b", lower))
    return term in lower


def is_crypto_relevant(article: Dict) -> bool:
    text = _article_text(article)
    if any(_contains_term(text, term) for term in CRYPTO_RELEVANCE_TERMS):
        return True
    if any(term in text for term in MACRO_RELEVANCE_TERMS):
        return True
    return False


def is_off_topic(article: Dict) -> bool:
    text = _article_text(article)
    if is_crypto_relevant(article):
        return False
    return any(term in text for term in OFF_TOPIC_TERMS)


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
        if _contains_term(text, keyword):
            score += weight

    source = article.get("source", "")
    score += SOURCE_BONUS.get(source, 0)

    for bad in EXCLUDE_KEYWORDS:
        if bad in text:
            score -= 15

    if is_fluff(article):
        score -= 20

    if is_off_topic(article):
        score -= 40

    if not is_crypto_relevant(article):
        score -= 25

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
    hard_signals = sum(
        1 for kw in (
            "etf", "sec", "fed", "billion", "regulation", "hack", "approval",
            "outflow", "inflow", "tokenization", "wall street",
        )
        if _contains_term(text, kw)
    )
    if hard_signals == 0 and score < min_short_score:
        score -= 5

    return score


def passes_short_filter(article: Dict, min_score: int = 12, max_age_hours: int = 24) -> bool:
    if is_fluff(article) or is_generic_roundup(article.get("title", "")):
        return False
    if is_off_topic(article) or not is_crypto_relevant(article):
        return False
    age_h = article_age_hours(article)
    if age_h is not None and age_h > max_age_hours:
        return False
    return score_article(article, min_short_score=min_score) >= min_score


def passes_telegram_filter(article: Dict, min_score: int = 6, max_age_hours: int = 48) -> bool:
    if is_fluff(article) or is_off_topic(article):
        return False
    if not is_crypto_relevant(article):
        return False
    age_h = article_age_hours(article)
    if age_h is not None and age_h > max_age_hours:
        return False
    return score_article(article) >= min_score


def extract_key_bullets(article: Dict, max_bullets: int = 3) -> List[str]:
    """Pull factual sentences from summary — never duplicate the headline."""
    title = article.get("title", "").strip()
    summary = article.get("summary", "").strip()
    title_key = re.sub(r"\W+", "", title.lower())
    candidates: List[Tuple[int, str]] = []

    for sentence in re.split(r"(?<=[.!?])\s+", summary):
        sentence = sentence.strip()
        if len(sentence) < 30:
            continue
        sent_key = re.sub(r"\W+", "", sentence.lower())
        if sent_key == title_key or title_key in sent_key and len(sent_key) < len(title_key) + 20:
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
        bullets.append(naturalize_text(clean))
        if len(bullets) >= max_bullets:
            break

    if not bullets and summary:
        fallback = summary[:200].rsplit(" ", 1)[0] + ("..." if len(summary) > 200 else "")
        bullets.append(naturalize_text(fallback))

    return bullets


def score_sentence(sentence: str) -> int:
    score = 0
    lower = sentence.lower()
    if FACT_SIGNAL_RE.search(sentence):
        score += 6
    for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
        if _contains_term(lower, keyword):
            score += min(weight, 4)
    if re.search(r"\d", sentence):
        score += 2
    return score


def build_hashtags(article: Dict, max_tags: int = 5) -> str:
    text = _article_text(article)
    tags: List[str] = []
    for keyword, tag in HASHTAG_MAP:
        if _contains_term(text, keyword) and tag not in tags:
            tags.append(tag)
        if len(tags) >= max_tags - 1:
            break
    tags.append("#CoinWire")
    return " ".join(tags[:max_tags])


def classify_telegram_tier(
    score: int,
    *,
    breaking_score: int = 22,
    insight_score: int = 18,
    strong_score: int = 15,
    min_score: int = 6,
) -> TelegramTier:
    if score < min_score:
        return "skip"
    if score >= breaking_score:
        return "breaking"
    if score >= insight_score:
        return "insight"
    if score >= strong_score:
        return "strong"
    return "standard"


TAKEAWAY_RULES: List[Tuple[tuple[str, ...], str]] = [
    (
        ("etf", "outflow", "inflow"),
        "ETF flow prints often lead spot BTC. Watch issuer totals next.",
    ),
    (
        ("sec", "regulation", "regulatory"),
        "Regulatory headlines hit exchange and large-cap risk appetite fast.",
    ),
    (
        ("lawsuit", "settlement"),
        "Legal moves matter when a listed crypto company is named. Check who is exposed.",
    ),
    (
        ("fed", "federal reserve", "interest rate", "rate cut", "rate hike", "inflation"),
        "Fed and macro prints drive risk-on/off across crypto.",
    ),
    (
        ("hack", "exploit", "breach"),
        "Security incidents can spark short-term selling. Confirm size before reacting.",
    ),
    (
        ("blackrock", "fidelity", "institutional", "wall street", "treasury"),
        "Big buyers support the long story; near-term price still follows liquidity.",
    ),
    (
        ("tokenization", "rwa"),
        "Tokenization points to where TradFi may come on-chain next.",
    ),
    (
        ("billion", "million"),
        "Large dollar figures usually mean treasury, ETF, or M&A size. Focus on the number.",
    ),
]


def build_market_takeaway(article: Dict) -> str:
    """Rule-based 'so what' line — humanized, no LLM."""
    from src.content.humanize_copy import humanize_takeaway

    text = _article_text(article)
    raw = ""
    for keywords, takeaway in TAKEAWAY_RULES:
        if any(_contains_term(text, keyword) for keyword in keywords):
            raw = takeaway
            break
    if not raw:
        if "bitcoin" in text or "ethereum" in text:
            raw = "Majors lead; watch BTC dominance and ETH follow-through."
        else:
            # Prefer no generic boilerplate — empty skips takeaway noise
            return ""
    return humanize_takeaway(naturalize_text(raw)) or naturalize_text(raw)


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def format_telegram_post_html(
    article: Dict,
    *,
    tier: TelegramTier = "standard",
    market_line: Optional[str] = None,
    include_insight: bool = False,
) -> str:
    """HTML post for Telegram — headline, bullets, optional takeaway."""
    max_bullets = 2 if tier in ("breaking", "insight", "strong") else 2
    bullets = extract_key_bullets(article, max_bullets=max_bullets)
    hashtags = build_hashtags(article, max_tags=4)
    source_label = _esc(article.get("source", "news").replace("_", " ").title())
    title = _esc(naturalize_text(article["title"]))

    lines: List[str] = []

    if market_line:
        lines.append(f"<i>{_esc(market_line)}</i>")
        lines.append("")

    if tier == "breaking":
        lines.append("🚨 <b>BREAKING</b>")
    elif tier == "insight":
        lines.append("💡 <b>MARKET TAKE</b>")
    elif tier == "strong":
        lines.append("📌 <b>KEY STORY</b>")
    else:
        lines.append("📰 <b>COIN WIRE</b>")

    lines.append(f"<b>{title}</b>")
    lines.append("")

    for bullet in bullets:
        lines.append(f"• {_esc(bullet)}")

    if include_insight or tier in ("breaking", "insight"):
        takeaway = build_market_takeaway(article)
        if takeaway:
            lines.append("")
            lines.append("💡 <b>Takeaway</b>")
            lines.append(_esc(takeaway))

    lines.extend([
        "",
        hashtags,
        "",
        f"📎 {_esc(source_label)}",
        "",
        "<i>Not financial advice. News and education only.</i>",
    ])
    return "\n".join(lines)


def format_telegram_post(article: Dict) -> str:
    """Rich post: headline + key bullets + hashtags + link."""
    bullets = extract_key_bullets(article, max_bullets=3)
    hashtags = build_hashtags(article)
    source_label = article.get("source", "news").replace("_", " ").title()

    lines = [f"📰 {naturalize_text(article['title'])}", ""]
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
