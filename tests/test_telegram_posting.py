"""Tests for smart Telegram posting and news tiers."""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.content.news_filter import (
    build_market_takeaway,
    classify_telegram_tier,
    format_telegram_post_html,
)
from src.content.telegram_posting import (
    DailyState,
    TelegramPostingConfig,
    decide_post,
    expected_min_posts,
)


def test_breaking_tier():
    assert classify_telegram_tier(25) == "breaking"
    assert classify_telegram_tier(18) == "insight"
    assert classify_telegram_tier(15) == "strong"
    assert classify_telegram_tier(8) == "standard"
    assert classify_telegram_tier(4) == "skip"


def test_takeaway_for_fed_story():
    article = {
        "title": "Fed holds rates steady, Bitcoin dips 2%",
        "summary": "The Federal Reserve kept interest rates unchanged.",
    }
    takeaway = build_market_takeaway(article)
    assert "Fed" in takeaway or "macro" in takeaway.lower()


def test_html_post_has_takeaway_for_insight():
    article = {
        "title": "SEC reviews new Bitcoin ETF filing from BlackRock",
        "summary": (
            "The SEC is reviewing a new filing. BlackRock expanded its ETF product line. "
            "Bitcoin traded near $104,000 after the announcement."
        ),
        "source": "the_block",
        "link": "https://example.com/story",
    }
    html_post = format_telegram_post_html(
        article,
        tier="insight",
        market_line="BTC $104,000 (+1.2%)",
        include_insight=True,
    )
    assert "<b>" in html_post
    assert "Takeaway" in html_post
    assert "SEC" in html_post or "BlackRock" in html_post


def test_decide_post_breaking_immediately():
    cfg = TelegramPostingConfig()
    state = DailyState(date="2026-06-16", post_count=2)
    article = {"score": 30, "title": "test"}
    ok, reason = decide_post(article, state, cfg)
    assert ok is True
    assert reason == "breaking_news"


def test_decide_post_respects_daily_max():
    cfg = TelegramPostingConfig(max_posts_per_day=8)
    state = DailyState(date="2026-06-16", post_count=8)
    article = {"score": 30}
    ok, reason = decide_post(article, state, cfg)
    assert ok is False
    assert reason == "daily_max_reached"


def test_time_of_day_cap_blocks_morning_spam():
    cfg = TelegramPostingConfig(max_posts_by_noon=3, max_posts_per_day=8)
    state = DailyState(date="2026-06-16", post_count=3)
    morning = datetime(2026, 6, 16, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    article = {"score": 30}
    ok, reason = decide_post(article, state, cfg, now=morning)
    assert ok is False
    assert reason == "time_of_day_cap"


def test_floor_expected_by_noon():
    noon = datetime(2026, 6, 16, 12, 15, tzinfo=ZoneInfo("America/New_York"))
    assert expected_min_posts(noon, ((8, 0), (12, 0), (17, 0))) == 2


def test_floor_overrides_time_cap():
    cfg = TelegramPostingConfig(max_posts_by_noon=3, min_posts_per_day=3)
    state = DailyState(date="2026-06-16", post_count=0)
    morning = datetime(2026, 6, 16, 8, 30, tzinfo=ZoneInfo("America/New_York"))
    article = {"score": 10}
    ok, reason = decide_post(article, state, cfg, now=morning)
    assert ok is True
    assert reason == "daily_floor"
