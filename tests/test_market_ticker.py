"""Tests for CoinGecko market ticker helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from src.content.market_ticker import (
    MarketQuote,
    _parse_quotes,
    fetch_market_ticker_line,
    format_market_snapshot,
)


def test_parse_quotes_btc_eth():
    data = {
        "bitcoin": {"usd": 104200, "usd_24h_change": 1.2},
        "ethereum": {"usd": 3450.5, "usd_24h_change": -0.4},
    }
    quotes = _parse_quotes(data)
    assert len(quotes) == 2
    assert quotes[0].symbol == "BTC"
    assert quotes[0].price_usd == 104200
    assert quotes[1].symbol == "ETH"


def test_format_short_positive_and_negative():
    btc = MarketQuote("BTC", 104200, 1.2)
    eth = MarketQuote("ETH", 3450.5, -0.4)
    assert "BTC $104,200 (+1.20%)" in btc.format_short()
    assert "ETH $3,450 (-0.40%)" in eth.format_short()


def test_fetch_market_ticker_line_from_quotes(monkeypatch):
    monkeypatch.setattr(
        "src.content.market_ticker.fetch_market_quotes",
        lambda: [
            MarketQuote("BTC", 100000, 2.0),
            MarketQuote("ETH", 3000, -1.0),
        ],
    )
    line = fetch_market_ticker_line()
    assert line is not None
    assert "BTC" in line
    assert "ETH" in line


def test_format_market_snapshot_english():
    quotes = [
        MarketQuote("BTC", 64061, 1.36),
        MarketQuote("ETH", 1905, 0.92),
        MarketQuote("SOL", 75.95, 0.60),
    ]
    text = format_market_snapshot(
        quotes, when=datetime(2026, 8, 17, tzinfo=timezone.utc)
    )
    assert text.startswith("Market snapshot, Aug 17")
    assert "Bitcoin $64,061 (+1.36%)" in text
    assert "Ethereum $1,905 (+0.92%)" in text
    assert "Solana $75.95 (+0.60%)" in text
    assert text.strip().endswith("24h change · CoinGecko")
    assert "📊" not in text


def test_format_market_snapshot_empty():
    assert format_market_snapshot([]) == ""
