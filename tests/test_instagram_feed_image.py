"""Instagram feed image helpers."""

from src.media.instagram_feed_image import pick_stock_keywords


def test_pick_stock_keywords_from_title():
    keys = pick_stock_keywords("Bitcoin ETF inflows hit new high", ["stock market"])
    assert "bitcoin" in keys[0] or "etf" in keys[0]


def test_pick_stock_keywords_fallback():
    keys = pick_stock_keywords("Markets update today")
    assert len(keys) >= 1
