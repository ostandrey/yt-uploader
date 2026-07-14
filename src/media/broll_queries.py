"""Category → stock search query packs for B-roll library fill."""

from __future__ import annotations

from typing import Dict, List

# Sources V1. Coverr can be added later as a driver.
SUPPORTED_SOURCES = ("pexels", "pixabay")

CATEGORY_QUERIES: Dict[str, List[str]] = {
    "bitcoin": [
        "bitcoin trading",
        "crypto chart screen",
        "candlestick trading monitor",
        "cryptocurrency office",
        "bitcoin laptop",
    ],
    "ethereum": [
        "ethereum",
        "blockchain network",
        "cryptocurrency technology",
        "digital finance laptop",
        "defi abstract",
    ],
    "macro": [
        "stock market ticker",
        "wall street",
        "federal reserve building",
        "inflation news",
        "trading floor",
        "financial district",
    ],
    "regulation": [
        "courthouse exterior",
        "government building",
        "legal documents desk",
        "compliance office",
        "capitol building",
    ],
    "security": [
        "cyber security",
        "hacking code screen",
        "digital lock",
        "server room",
        "password security",
    ],
    "defi": [
        "digital finance",
        "smart contract abstract",
        "tokenization",
        "blockchain technology",
        "fintech mobile",
    ],
    "default": [
        "city night finance",
        "money abstract",
        "business technology",
        "global markets",
    ],
}
