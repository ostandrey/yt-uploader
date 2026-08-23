"""Rules-based price archive and Numbers that matter formatter."""

from __future__ import annotations

from src.content.market_ticker import MarketQuote
from src.content.price_history import (
    build_numbers_compare,
    find_compare_day,
    format_numbers_that_matter,
    load_history,
    record_quotes,
)


def test_record_and_load_quotes(tmp_path):
    path = tmp_path / "price_history.json"
    record_quotes(
        [MarketQuote("BTC", 100000), MarketQuote("ETH", 3000)],
        "2026-08-16",
        path=path,
    )
    record_quotes([MarketQuote("BTC", 104000)], "2026-08-23", path=path)
    history = load_history(path)
    assert history["2026-08-16"]["BTC"] == 100000
    assert history["2026-08-16"]["ETH"] == 3000
    assert history["2026-08-23"]["BTC"] == 104000


def test_find_compare_day_prefers_exact_lookback():
    history = {
        "2026-08-14": {"BTC": 1},
        "2026-08-16": {"BTC": 1},
        "2026-08-17": {"BTC": 1},
        "2026-08-23": {"BTC": 1},
    }
    assert find_compare_day(history, "2026-08-23", lookback_days=7) == "2026-08-16"


def test_find_compare_day_uses_slack_when_exact_missing():
    history = {
        "2026-08-15": {"BTC": 1},
        "2026-08-23": {"BTC": 1},
    }
    assert find_compare_day(history, "2026-08-23", lookback_days=7) == "2026-08-15"


def test_build_numbers_skips_flat_move():
    result = build_numbers_compare(
        {"BTC": 101000, "ETH": 3050},
        {"BTC": 100000, "ETH": 3000},
        min_abs_pct=2.0,
    )
    assert result["text"] == ""
    assert result["reason"] == "below_threshold"


def test_build_numbers_formats_btc_eth():
    result = build_numbers_compare(
        {"BTC": 110000, "ETH": 2800},
        {"BTC": 100000, "ETH": 3000},
        min_abs_pct=2.0,
    )
    text = result["text"]
    assert "BTC $110,000 vs $100,000" in text
    assert "+10.0% over 7 days." in text
    assert "ETH $2,800 vs $3,000" in text
    assert "-6.7% over 7 days." in text
    assert text.strip().endswith("#bitcoin")
    assert "watching" not in text.lower()
    assert "?" not in text


def test_format_numbers_that_matter_end_to_end(tmp_path):
    path = tmp_path / "price_history.json"
    record_quotes(
        [MarketQuote("BTC", 90000), MarketQuote("ETH", 2500)],
        "2026-08-16",
        path=path,
    )
    record_quotes(
        [MarketQuote("BTC", 99000), MarketQuote("ETH", 2700)],
        "2026-08-23",
        path=path,
    )
    built = format_numbers_that_matter(
        today="2026-08-23",
        path=path,
        min_abs_pct=2.0,
    )
    assert built["reason"] == "ok"
    assert built["compare_day"] == "2026-08-16"
    assert "BTC $99,000 vs $90,000" in built["text"]
