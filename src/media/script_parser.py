"""
Parse Short scripts into sentences, B-roll search terms, and on-screen stats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_TO_PERCENT = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}

PEXELS_QUERIES = {
    "bitcoin": "bitcoin chart trading screen monitor",
    "btc": "bitcoin price chart red falling",
    "ethereum": "ethereum crypto chart screen",
    "eth": "ethereum price chart trading",
    "fed": "interest rate chart economy graph",
    "federal": "stock market chart trading desk",
    "reserve": "central bank interest rates data",
    "rates": "interest rates chart inflation graph",
    "rate": "federal funds rate chart screen",
    "market": "stock market ticker trading screen",
    "crypto": "cryptocurrency trading charts monitor",
    "cryptocurrency": "crypto trading multiple screens",
    "trading": "stock trading charts monitor desk",
    "hawkish": "stock market red chart falling",
    "policy": "inflation economy data chart screen",
    "analyst": "financial charts trading monitor",
    "altcoin": "cryptocurrency exchange trading screen",
    "track": "crypto news app smartphone chart",
    "sensitive": "economy stock market data screen",
    "daily": "financial news alert smartphone",
    "expected": "stock market analysis chart screen",
    "unchanged": "interest rates unchanged chart",
    "lower": "stock market red chart decline",
    "falling": "bitcoin price falling chart",
}


@dataclass
class StatOverlay:
    text: str
    keyword: str
    display_sec: float = 3.0
    show_from_start: bool = False


def split_sentences(text: str) -> List[str]:
    chunks = SENTENCE_SPLIT.split(text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _tokenize_for_search(sentence: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z]+", sentence.lower())
    return tokens


def sentence_search_keywords(sentence: str) -> List[str]:
    """Return 1-3 Pexels-friendly queries derived from a sentence."""
    tokens = _tokenize_for_search(sentence)
    queries: List[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token in PEXELS_QUERIES and token not in seen:
            queries.append(PEXELS_QUERIES[token])
            seen.add(token)

    if not queries:
        if any(t in tokens for t in ("bitcoin", "btc", "crypto")):
            queries.append("bitcoin chart trading screen")
        elif any(t in tokens for t in ("fed", "federal", "reserve", "rates")):
            queries.append("interest rate chart economy graph")
        elif any(t in tokens for t in ("ethereum", "eth")):
            queries.append("ethereum price chart trading")
        else:
            queries.append("stock market chart trading screen")

    return queries[:3]


def plan_broll_segments(
    sentences: List[str],
    sentence_durations: List[float],
    min_sec: float = 2.0,
    max_sec: float = 2.5,
) -> List[dict]:
    """Fast cuts every 1.5–2s, rotating keywords within each sentence."""
    segments: List[dict] = []

    for sentence, sent_dur in zip(sentences, sentence_durations):
        keywords = sentence_search_keywords(sentence)
        remaining = max(sent_dur, min_sec)
        keyword_index = 0

        while remaining > 0.1:
            clip_dur = min(max_sec, max(min_sec, remaining))
            if remaining < min_sec + 0.1:
                clip_dur = remaining

            segments.append({
                "keyword": keywords[keyword_index % len(keywords)],
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
        return "Markets remain volatile — follow for the next shift."
    if "bitcoin" in lower or "crypto" in lower:
        return "Crypto moves fast — follow for daily updates."
    sentences = split_sentences(script)
    if len(sentences) >= 2:
        candidate = sentences[-2].strip()
        if len(candidate) > 55:
            candidate = candidate[:52] + "..."
        return candidate
    return "Follow for the next market shift."
