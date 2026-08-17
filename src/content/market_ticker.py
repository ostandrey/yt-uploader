"""
Live BTC/ETH prices (CoinGecko free API) for Telegram and video overlays.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import requests

log = logging.getLogger(__name__)

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,solana,ripple,binancecoin"
    "&vs_currencies=usd&include_24hr_change=true"
)

TICKER_IDS = (("bitcoin", "BTC"), ("ethereum", "ETH"))
SNAPSHOT_IDS = TICKER_IDS + (
    ("solana", "SOL"),
    ("ripple", "XRP"),
    ("binancecoin", "BNB"),
)
COIN_IDS = TICKER_IDS

SNAPSHOT_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "XRP": "XRP",
    "BNB": "BNB",
}


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price_usd: float
    change_24h_pct: Optional[float] = None

    def format_price(self) -> str:
        if self.price_usd >= 1000:
            return f"${self.price_usd:,.0f}"
        return f"${self.price_usd:,.2f}"

    def format_change(self) -> str:
        if self.change_24h_pct is None:
            return ""
        sign = "+" if self.change_24h_pct >= 0 else ""
        return f"{sign}{self.change_24h_pct:.2f}%"

    def format_short(self) -> str:
        change = self.format_change()
        if not change:
            return f"{self.symbol} {self.format_price()}"
        return f"{self.symbol} {self.format_price()} ({change})"


def _parse_quotes(data: dict, ids: tuple = TICKER_IDS) -> List[MarketQuote]:
    quotes: List[MarketQuote] = []
    for coin_id, label in ids:
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


def fetch_market_quotes(*, snapshot: bool = False) -> List[MarketQuote]:
    """Return quotes, or empty list on API failure. Ticker defaults to BTC/ETH."""
    ids = SNAPSHOT_IDS if snapshot else TICKER_IDS
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
    return _parse_quotes(data, ids)


def fetch_market_ticker_line() -> Optional[str]:
    """e.g. BTC $104,200 (+1.20%) · ETH $3,450 (-0.40%)"""
    quotes = fetch_market_quotes()
    if not quotes:
        return None
    return " · ".join(q.format_short() for q in quotes)


def format_market_snapshot(
    quotes: List[MarketQuote],
    *,
    when: Optional[datetime] = None,
) -> str:
    """English utility post. Empty string if there are no quotes."""
    if not quotes:
        return ""
    stamp = when or datetime.now(timezone.utc)
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    header = f"Market snapshot, {months[stamp.month - 1]} {stamp.day}"
    lines = [header]
    for quote in quotes:
        name = SNAPSHOT_NAMES.get(quote.symbol, quote.symbol)
        change = quote.format_change()
        if change:
            lines.append(f"{name} {quote.format_price()} ({change})")
        else:
            lines.append(f"{name} {quote.format_price()}")
    lines.append("")
    lines.append("24h change · CoinGecko")
    return "\n".join(lines)
