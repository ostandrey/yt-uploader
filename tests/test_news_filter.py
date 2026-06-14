"""Tests for Coin Wire news scoring and Telegram formatting."""

from src.content.news_filter import (
    build_hashtags,
    extract_key_bullets,
    is_fluff,
    passes_short_filter,
    score_article,
)


def test_fluff_rejected():
    article = {
        "title": "This memecoin could hit $1 million says analyst",
        "summary": "Price prediction for the next pump season.",
        "source": "decrypt",
        "published": None,
    }
    assert is_fluff(article)
    assert not passes_short_filter(article)


def test_serious_article_scores_high():
    article = {
        "title": "Spot Bitcoin ETFs see $500M outflow as SEC reviews new filing",
        "summary": (
            "U.S. spot Bitcoin ETFs recorded $500 million in outflows on Friday. "
            "The SEC is reviewing a new Ethereum staking product from BlackRock."
        ),
        "source": "the_block",
        "published": None,
    }
    assert score_article(article) >= 12
    assert passes_short_filter(article)


def test_telegram_bullets_and_tags():
    article = {
        "title": "Fed holds rates steady, Bitcoin dips 2%",
        "summary": (
            "The Federal Reserve kept interest rates unchanged. "
            "Bitcoin fell 2% after the announcement. "
            "Traders now watch the September dot plot."
        ),
        "source": "coindesk",
        "published": None,
    }
    bullets = extract_key_bullets(article)
    assert len(bullets) >= 1
    tags = build_hashtags(article)
    assert "#Bitcoin" in tags or "#Fed" in tags
    assert "#CoinWire" in tags
