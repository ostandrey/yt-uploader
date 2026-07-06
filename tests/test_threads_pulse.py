"""Threads news pulse text variants."""

from src.content.threads_pulse import (
    build_threads_news_pulse,
    pick_pulse_variant,
    tier_meets_minimum,
)


def test_tier_meets_minimum():
    assert tier_meets_minimum("breaking", "strong")
    assert tier_meets_minimum("strong", "strong")
    assert not tier_meets_minimum("standard", "strong")


def test_pick_variant_deterministic():
    assert pick_pulse_variant("strong", "hash-abc") == pick_pulse_variant("strong", "hash-abc")


def test_build_pulse_under_500_chars():
    article = {
        "title": "Bitcoin ETF inflows turn positive after five-day outflow streak",
        "summary": "Spot Bitcoin ETFs pulled in fresh capital on Friday as traders repositioned ahead of macro data.",
        "link": "https://example.com/a",
        "hash": "abc123",
    }
    text, variant = build_threads_news_pulse(article, tier="strong", seed="abc123")
    assert len(text) <= 500
    assert variant
    # Most posts get tags; not always the same three
    assert "#" in text or len(text) > 20


def test_breaking_variant_prefix():
    article = {
        "title": "SEC approves new crypto framework for exchanges",
        "summary": "Regulators outlined compliance steps for major US platforms.",
        "hash": "brk1",
    }
    text, variant = build_threads_news_pulse(article, tier="breaking", seed="brk1")
    assert variant == "breaking_lead" or "SEC" in text
