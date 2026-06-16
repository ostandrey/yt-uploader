"""
Live BTC/ETH line for Telegram posts (CoinGecko free API).
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
)


def fetch_market_ticker_line() -> Optional[str]:
    """e.g. BTC $104,200 (+1.2%) · ETH $3,450 (-0.4%)"""
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
        return None

    parts: list[str] = []
    for coin_id, label in (("bitcoin", "BTC"), ("ethereum", "ETH")):
        row = data.get(coin_id, {})
        price = row.get("usd")
        change = row.get("usd_24h_change")
        if price is None:
            continue
        price_str = f"${price:,.0f}" if price >= 1000 else f"${price:,.2f}"
        if change is not None:
            sign = "+" if change >= 0 else ""
            parts.append(f"{label} {price_str} ({sign}{change:.1f}%)")
        else:
            parts.append(f"{label} {price_str}")

    return " · ".join(parts) if parts else None
