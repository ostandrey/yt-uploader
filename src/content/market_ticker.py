"""
Live BTC/ETH prices (CoinGecko free API) for Telegram and video overlays.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

log = logging.getLogger(__name__)

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
)

COIN_IDS = (("bitcoin", "BTC"), ("ethereum", "ETH"))


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price_usd: float
    change_24h_pct: Optional[float] = None

    def format_short(self) -> str:
        price_str = (
            f"${self.price_usd:,.0f}"
            if self.price_usd >= 1000
            else f"${self.price_usd:,.2f}"
        )
        if self.change_24h_pct is None:
            return f"{self.symbol} {price_str}"
        sign = "+" if self.change_24h_pct >= 0 else ""
        return f"{self.symbol} {price_str} ({sign}{self.change_24h_pct:.1f}%)"


def _parse_quotes(data: dict) -> List[MarketQuote]:
    quotes: List[MarketQuote] = []
    for coin_id, label in COIN_IDS:
        row = data.get(coin_id, {})
        price = row.get("usd")
        if price is None:
            continue
        quotes.append(MarketQuote(
            symbol=label,
            price_usd=float(price),
            change_24h_pct=row.get("usd_24h_change"),
        ))
    return quotes


def fetch_market_quotes() -> List[MarketQuote]:
    """Return BTC/ETH quotes, or empty list on API failure."""
    try:
        response = requests.get(
            COINGECKO_URL,
            timeout=10,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("Market ticker unavailable: %s", exc)
        return []
    return _parse_quotes(data)


def fetch_market_ticker_line() -> Optional[str]:
    """e.g. BTC $104,200 (+1.2%) · ETH $3,450 (-0.4%)"""
    quotes = fetch_market_quotes()
    if not quotes:
        return None
    return " · ".join(q.format_short() for q in quotes)
