"""
Parse Short scripts into sentences, B-roll search terms, and on-screen stats.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import List, Optional

from src.media.broll_library import CATEGORY_ALIASES, normalize_category

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_TO_PERCENT = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}

# Multi-variant Pexels queries — one random pick per token per render.
PEXELS_QUERIES: dict[str, list[str]] = {
    "bitcoin": [
        "bitcoin gold coin closeup",
        "bitcoin chart trading screen monitor",
        "cryptocurrency trading desk multiple monitors",
    ],
    "btc": [
        "bitcoin price chart red falling",
        "bitcoin coin spinning macro",
        "crypto exchange trading floor",
    ],
    "ethereum": [
        "ethereum crypto chart screen",
        "ethereum blockchain network visualization",
        "defi protocol dashboard screen",
    ],
    "eth": [
        "ethereum price chart trading",
        "ethereum coin digital art",
        "crypto wallet app smartphone",
    ],
    "fed": [
        "federal reserve building exterior",
        "interest rate chart economy graph",
        "central bank press conference",
    ],
    "federal": [
        "stock market chart trading desk",
        "economy inflation data screen",
        "wall street trading floor",
    ],
    "reserve": [
        "central bank interest rates data",
        "monetary policy meeting room",
        "economy news headline screen",
    ],
    "rates": [
        "interest rates chart inflation graph",
        "bond yield curve screen",
        "federal funds rate chart screen",
    ],
    "rate": [
        "federal funds rate chart screen",
        "interest rate decision news",
        "economy data dashboard",
    ],
    "inflation": [
        "inflation economy data chart screen",
        "consumer price index graph",
        "grocery prices rising news",
    ],
    "etf": [
        "etf stock market chart screen",
        "institutional investor trading desk",
        "fund flows financial data",
    ],
    "market": [
        "stock market ticker trading screen",
        "wall street bull statue",
        "financial district skyline night",
    ],
    "crypto": [
        "cryptocurrency trading charts monitor",
        "crypto exchange app smartphone",
        "blockchain network nodes animation",
    ],
    "cryptocurrency": [
        "crypto trading multiple screens",
        "digital currency coins closeup",
        "blockchain technology abstract",
    ],
    "trading": [
        "stock trading charts monitor desk",
        "day trader multiple screens",
        "financial charts candlestick screen",
    ],
    "hawkish": [
        "stock market red chart falling",
        "bear market decline graph",
        "trader worried looking screen",
    ],
    "policy": [
        "inflation economy data chart screen",
        "government policy document signing",
        "economic summit conference",
    ],
    "analyst": [
        "financial charts trading monitor",
        "business analyst laptop data",
        "market research report screen",
    ],
    "altcoin": [
        "cryptocurrency exchange trading screen",
        "altcoin portfolio app",
        "crypto market cap ranking",
    ],
    "sec": [
        "sec regulation courthouse",
        "legal documents financial compliance",
        "government hearing courtroom",
    ],
    "regulation": [
        "financial regulation documents",
        "compliance audit office",
        "law gavel courtroom",
    ],
    "lawsuit": [
        "courtroom judge gavel",
        "legal papers signing",
        "lawyer office meeting",
    ],
    "hack": [
        "cybersecurity hacker screen code",
        "data breach alert notification",
        "network security firewall",
    ],
    "exploit": [
        "cyber attack warning screen",
        "security vulnerability code",
        "hacker typing dark room",
    ],
    "defi": [
        "defi protocol dashboard",
        "decentralized finance app",
        "liquidity pool animation",
    ],
    "tokenization": [
        "digital asset token blockchain",
        "real estate tokenization concept",
        "smart contract code screen",
    ],
    "stablecoin": [
        "stablecoin dollar peg chart",
        "usdc usdt crypto coins",
        "digital dollar concept",
    ],
    "treasury": [
        "us treasury building",
        "government bonds chart",
        "national debt graph screen",
    ],
    "track": [
        "crypto news app smartphone",
        "financial alert notification phone",
        "market tracker dashboard",
    ],
    "sensitive": [
        "economy stock market data screen",
        "volatile market chart red green",
        "trader stressed multiple monitors",
    ],
    "daily": [
        "financial news alert smartphone",
        "morning market briefing laptop",
        "news headline scroll screen",
    ],
    "expected": [
        "stock market analysis chart screen",
        "earnings forecast graph",
        "analyst prediction dashboard",
    ],
    "unchanged": [
        "interest rates unchanged chart",
        "flat market sideways trading",
        "steady economy data screen",
    ],
    "lower": [
        "stock market red chart decline",
        "bitcoin price falling chart",
        "bearish candlestick pattern",
    ],
    "falling": [
        "bitcoin price falling chart",
        "red stock market decline",
        "crypto crash news headline",
    ],
}

CATEGORY_FALLBACKS: dict[str, list[str]] = {
    "_macro": [
        "stock market chart trading screen",
        "interest rate chart economy graph",
        "wall street financial district",
        "economy news data dashboard",
    ],
    "_default": [
        "financial charts trading monitor",
        "business news smartphone app",
        "stock market ticker screen",
        "cryptocurrency trading desk",
    ],
}

TOKEN_CATEGORIES: dict[str, str] = {
    **{k: v for k, v in CATEGORY_ALIASES.items()},
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "altcoin": "ethereum",
    "crypto": "bitcoin",
    "cryptocurrency": "bitcoin",
    "trading": "macro",
    "hawkish": "macro",
    "policy": "macro",
    "analyst": "macro",
    "track": "macro",
    "sensitive": "macro",
    "daily": "macro",
    "expected": "macro",
    "unchanged": "macro",
    "lower": "macro",
    "falling": "bitcoin",
    "sec": "regulation",
    "regulation": "regulation",
    "lawsuit": "regulation",
    "hack": "security",
    "exploit": "security",
    "defi": "defi",
    "tokenization": "defi",
    "stablecoin": "defi",
}


@dataclass
class StatOverlay:
    text: str
    keyword: str
    display_sec: float = 3.0
    show_from_start: bool = False


@dataclass
class BrollTerm:
    query: str
    category: str
    token: str = ""


def split_sentences(text: str) -> List[str]:
    chunks = SENTENCE_SPLIT.split(text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _tokenize_for_search(sentence: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z]+", sentence.lower())
    return tokens


def token_category(token: str) -> str:
    return normalize_category(TOKEN_CATEGORIES.get(token, token))


def pick_pexels_query(token: str) -> BrollTerm:
    """Pick a random Pexels query and library category for a token."""
    variants = PEXELS_QUERIES.get(token)
    if variants:
        return BrollTerm(
            query=random.choice(variants),
            category=token_category(token),
            token=token,
        )
    return pick_fallback_query("macro" if token in ("fed", "federal", "reserve") else "default")


def pick_fallback_query(kind: str = "default") -> BrollTerm:
    key = "_macro" if kind == "macro" else "_default"
    category = "macro" if kind == "macro" else "default"
    return BrollTerm(
        query=random.choice(CATEGORY_FALLBACKS[key]),
        category=category,
        token=kind,
    )


def sentence_broll_terms(sentence: str) -> List[BrollTerm]:
    """Return 1-3 B-roll search terms derived from a sentence."""
    tokens = _tokenize_for_search(sentence)
    terms: List[BrollTerm] = []
    seen_tokens: set[str] = set()

    for token in tokens:
        if token in PEXELS_QUERIES and token not in seen_tokens:
            terms.append(pick_pexels_query(token))
            seen_tokens.add(token)

    if not terms:
        if any(t in tokens for t in ("bitcoin", "btc", "crypto")):
            terms.append(pick_pexels_query("bitcoin"))
        elif any(t in tokens for t in ("fed", "federal", "reserve", "rates")):
            terms.append(pick_fallback_query("macro"))
        elif any(t in tokens for t in ("ethereum", "eth")):
            terms.append(pick_pexels_query("ethereum"))
        else:
            terms.append(pick_fallback_query("default"))

    return terms[:3]


def sentence_search_keywords(sentence: str) -> List[str]:
    """Return 1-3 Pexels-friendly queries derived from a sentence."""
    return [t.query for t in sentence_broll_terms(sentence)]


def plan_broll_segments(
    sentences: List[str],
    sentence_durations: List[float],
    min_sec: float = 2.0,
    max_sec: float = 2.5,
) -> List[dict]:
    """Fast cuts every 1.5–2s, rotating keywords within each sentence."""
    segments: List[dict] = []

    for sentence, sent_dur in zip(sentences, sentence_durations):
        terms = sentence_broll_terms(sentence)
        remaining = max(sent_dur, min_sec)
        keyword_index = 0

        while remaining > 0.1:
            clip_dur = min(max_sec, max(min_sec, remaining))
            if remaining < min_sec + 0.1:
                clip_dur = remaining

            term = terms[keyword_index % len(terms)]
            segments.append({
                "keyword": term.query,
                "category": term.category,
                "duration": round(clip_dur, 2),
                "sentence": sentence,
            })
            remaining -= clip_dur
            keyword_index += 1

    return segments


def _word_to_number(word: str) -> Optional[int]:
    clean = word.lower().strip(".,!?")
    if clean.isdigit():
        return int(clean)
    return WORD_TO_PERCENT.get(clean)


def extract_stat_overlays(script: str) -> List[StatOverlay]:
    """
    Pull headline stats for on-screen overlays, e.g. 'BTC -4%'.
    """
    overlays: List[StatOverlay] = []
    lower = script.lower()

    percent_match = re.search(
        r"(bitcoin|btc|ethereum|eth|crypto)\s+.{0,40}?"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+percent",
        lower,
    )
    if percent_match:
        asset = percent_match.group(1)
        num = _word_to_number(percent_match.group(2))
        if num is not None:
            prefix = "BTC" if asset in ("bitcoin", "btc") else asset.upper()[:3]
            overlays.append(StatOverlay(
                text=f"{prefix} -{num}%",
                keyword=asset,
                show_from_start=True,
            ))

    pct_symbol = re.search(
        r"(bitcoin|btc)\s+(?:dropped?|fell|down)\s+(\d+)%",
        lower,
    )
    if pct_symbol:
        num = int(pct_symbol.group(2))
        overlays.append(StatOverlay(
            text=f"BTC -{num}%",
            keyword="bitcoin",
            show_from_start=True,
        ))

    eth_match = re.search(
        r"ethereum\s+.{0,40}?(?:falling|lower).{0,20}?"
        r"(three|four|five|two|one|\d+)\s+percent",
        lower,
    )
    if eth_match:
        num = _word_to_number(eth_match.group(1))
        if num is not None:
            overlays.append(StatOverlay(
                text=f"ETH -{num}%",
                keyword="ethereum",
                display_sec=2.5,
            ))

    return overlays[:2]


def extract_outro_summary(script: str) -> str:
    """One-line value hook for the outro card."""
    lower = script.lower()
    if "volatile" in lower or "sensitive" in lower or "fed" in lower:
        return "Markets remain volatile - follow for the next shift."
    if "bitcoin" in lower or "crypto" in lower:
        return "Crypto moves fast - follow for daily updates."
    sentences = split_sentences(script)
    if len(sentences) >= 2:
        candidate = sentences[-2].strip()
        if len(candidate) > 55:
            candidate = candidate[:52] + "..."
        return candidate
    return "Follow for the next market shift."
