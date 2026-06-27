"""Tests for CoinGecko market ticker helpers."""

from __future__ import annotations

from src.content.market_ticker import MarketQuote, _parse_quotes, fetch_market_ticker_line


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
    assert "BTC $104,200 (+1.2%)" in btc.format_short()
    assert "ETH $3,450 (-0.4%)" in eth.format_short()


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
