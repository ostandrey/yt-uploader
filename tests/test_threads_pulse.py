"""Threads news pulse — copy variants + desk-only queue."""

from src.content.news_filter import extract_key_bullets
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
    assert pick_pulse_variant("strong", "hash-abc") == pick_pulse_variant(
        "strong", "hash-abc"
    )


def test_build_pulse_under_500_chars():
    article = {
        "title": "Bitcoin ETF inflows turn positive after five-day outflow streak",
        "summary": (
            "Spot Bitcoin ETFs pulled in fresh capital on Friday as traders "
            "repositioned ahead of macro data."
        ),
        "link": "https://example.com/a",
        "hash": "abc123",
    }
    text, variant = build_threads_news_pulse(article, tier="strong", seed="abc123")
    assert len(text) <= 500
    assert variant
    assert "#" in text or len(text) > 20


def test_breaking_variant_has_text():
    article = {
        "title": "SEC approves new crypto framework for exchanges",
        "summary": "Regulators outlined compliance steps for major US platforms.",
        "hash": "brk1",
    }
    text, variant = build_threads_news_pulse(article, tier="breaking", seed="brk1")
    assert text
    assert variant


def test_news_pulse_desk_only_queues(tmp_path, monkeypatch):
    from src.desk import catalog, db
    from src.publishers.threads_pulse import ThreadsPulseConfig, maybe_post_news_pulse

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    monkeypatch.setattr(catalog, "EDITORIAL_LOCK_FILE", tmp_path / "editorial.lock")
    monkeypatch.setattr(
        "src.publishers.threads_pulse.STATE_FILE",
        tmp_path / "threads_daily_state.json",
    )
    monkeypatch.setattr(
        "src.desk.push.notify_desk_push",
        lambda *a, **k: {"reason": "ok", "sent": 0, "subs": 0},
    )

    cfg = ThreadsPulseConfig(
        enabled=True,
        desk_only=True,
        min_tier="strong",
        max_per_day=3,
        cooldown_minutes=0,
        timezone="America/New_York",
    )
    article = {
        "title": "Bitcoin ETF inflows hit a fresh high",
        "summary": "Issuers reported strong demand as traders rotated into spot products.",
        "hash": "desk-news-1",
    }
    result = maybe_post_news_pulse(
        article,
        "strong",
        cfg,
        state_path=tmp_path / "threads_daily_state.json",
    )
    assert result.get("desk_queued") is True
    assert result.get("posted") is False
    items = catalog.load_editorial_items(scope="all")
    assert len(items) == 1
    assert items[0]["kind"] == "news"
    assert "Threads" in items[0]["label"]


def test_desk_only_not_overridden_by_auto_publish():
    from src.publishers.threads_pulse import ThreadsPulseConfig

    cfg = ThreadsPulseConfig.from_config(
        {
            "publishing": {
                "threads": {
                    "news_pulse": {
                        "enabled": True,
                        "desk_only": True,
                        "auto_publish": True,
                    }
                }
            },
            "automation": {"timezone": "UTC"},
        }
    )
    assert cfg.desk_only is True


def test_pulse_does_not_reuse_telegram_bullets():
    article = {
        "title": "CFTC to Meet on Crypto Regulations on Aug. 20",
        "summary": (
            "The CFTC will hold a meeting for its Innovation Advisory Committee "
            "on Aug. 20 to address regulation related to crypto assets, artificial "
            "intelligence, and prediction markets."
        ),
        "hash": "cftc1",
    }
    text, _ = build_threads_news_pulse(article, tier="strong", seed="cftc1")
    bullets = extract_key_bullets(article, max_bullets=3)
    for bullet in bullets:
        assert bullet not in text
