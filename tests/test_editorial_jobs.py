"""Editorial jobs: reflection selection, caps, market snapshot, numbers."""

from __future__ import annotations

from datetime import datetime, timezone

from src.content.editorial_jobs import (
    pick_reflection_pair,
    post_market_snapshot,
    post_numbers_that_matter,
    post_threads_recap,
    post_threads_reflection,
)
from src.content.market_ticker import MarketQuote
from src.content.price_history import record_quotes


def test_pick_reflection_pair_flow_vs_regulatory():
    events = [
        {
            "title": "BlackRock Bitcoin ETF inflows hit $4.6B in three days",
            "tier": "breaking",
            "summary": "Fastest pace since launch.",
        },
        {
            "title": "CFTC set Aug. 20 for a committee meeting on crypto",
            "tier": "strong",
            "summary": "Agenda covers AI and prediction markets.",
        },
        {
            "title": "Solana NFT volume ticked up",
            "tier": "standard",
            "summary": "",
        },
    ]
    pair = pick_reflection_pair(events)
    assert pair is not None
    top, secondary = pair
    assert "BlackRock" in top["title"]
    assert "CFTC" in secondary["title"]


def test_pick_reflection_pair_needs_two_stories():
    assert pick_reflection_pair([{"title": "Only one story", "tier": "breaking"}]) is None
    assert pick_reflection_pair([]) is None


def _config():
    return {
        "publishing": {"editorial": {"opinion_per_week": 3, "threads_reflection": True}},
        "automation": {"timezone": "UTC"},
    }


def test_reflection_skips_when_opinion_cap_full(tmp_path, monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    monkeypatch.setattr("src.content.editorial_log.LOG_FILE", tmp_path / "log.json")
    from src.content.editorial_jobs import _save_state

    _save_state({"week": "2099-W01", "opinion": 3, "reflection": 0}, tmp_path / "state.json")
    # Force week key to match saved state
    monkeypatch.setattr("src.content.editorial_jobs._week_key", lambda tz: "2099-W01")
    result = post_threads_reflection(type("P", (), {})(), _config(), dry_run=True)
    assert result["reason"] == "opinion_cap"


def test_reflection_skips_one_event(tmp_path, monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    monkeypatch.setattr("src.content.editorial_log.LOG_FILE", tmp_path / "log.json")
    from src.content.editorial_log import append_event

    append_event(
        kind="telegram",
        title="BlackRock ETF inflows hit $4.6B",
        tier="breaking",
        path=tmp_path / "log.json",
    )
    result = post_threads_reflection(type("P", (), {})(), _config(), dry_run=True)
    assert result["reason"] == "need_two_stories"


def test_friday_recap_queues_reflection(tmp_path, monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    monkeypatch.setattr("src.content.editorial_log.LOG_FILE", tmp_path / "log.json")
    pushed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "src.content.editorial_jobs._push_desk_item",
        lambda kind, label, text: pushed.append((kind, text)),
    )
    from src.content.editorial_log import append_event

    append_event(
        kind="telegram",
        title="BlackRock Bitcoin ETF inflows hit $4.6B in three days",
        tier="breaking",
        path=tmp_path / "log.json",
    )
    append_event(
        kind="telegram",
        title="CFTC set Aug. 20 for a committee meeting on crypto",
        tier="strong",
        path=tmp_path / "log.json",
    )
    publisher = type("P", (), {"post_to_channel": lambda self, text: None})()
    result = post_threads_recap(publisher, _config(), dry_run=True)
    kinds = [item[0] for item in pushed]
    assert "recap" in kinds
    assert "reflection" in kinds
    assert "reflection" in result
    reflection = result["reflection"]["text"]
    assert "Telegram" not in kinds
    assert len(reflection) <= 700
    assert "context" not in kinds


def test_snapshot_skips_empty_quotes(monkeypatch):
    monkeypatch.setattr(
        "src.content.editorial_jobs.fetch_market_quotes", lambda snapshot=False: []
    )
    result = post_market_snapshot(type("P", (), {})(), _config(), dry_run=True)
    assert result["reason"] == "no_quotes"


def test_snapshot_formats_without_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    monkeypatch.setattr(
        "src.content.editorial_jobs.fetch_market_quotes",
        lambda snapshot=False: [MarketQuote("BTC", 64061, 1.36), MarketQuote("ETH", 1905, 0.92)],
    )
    result = post_market_snapshot(type("P", (), {})(), _config(), dry_run=True)
    assert result["dry_run"] is True
    assert "Bitcoin $64,061" in result["text"]
    assert "CoinGecko" in result["text"]
    assert "📊" not in result["text"]


def _numbers_config(**extra):
    cfg = _config()
    cfg["publishing"]["editorial"].update(
        {
            "numbers_that_matter": True,
            "numbers_per_week": 3,
            "numbers_min_pct": 2.0,
            "numbers_lookback_days": 7,
        }
    )
    cfg["publishing"]["editorial"].update(extra)
    return cfg


def test_numbers_skips_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    hist = tmp_path / "price_history.json"
    monkeypatch.setattr("src.content.price_history.HISTORY_FILE", hist)
    monkeypatch.setattr(
        "src.content.editorial_jobs.fetch_market_quotes",
        lambda snapshot=False: [
            MarketQuote("BTC", 101000, 0.5),
            MarketQuote("ETH", 3050, 0.5),
        ],
    )
    from datetime import date as date_cls, timedelta, timezone as tz

    today = datetime.now(tz.utc).strftime("%Y-%m-%d")
    week_ago = (date_cls.fromisoformat(today) - timedelta(days=7)).isoformat()
    record_quotes(
        [MarketQuote("BTC", 100000), MarketQuote("ETH", 3000)],
        week_ago,
        path=hist,
    )
    result = post_numbers_that_matter(
        type("P", (), {})(), _numbers_config(), dry_run=True
    )
    assert result["posted"] is False
    assert result["reason"] == "below_threshold"


def test_numbers_formats_contrast(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    hist = tmp_path / "price_history.json"
    monkeypatch.setattr("src.content.price_history.HISTORY_FILE", hist)
    monkeypatch.setattr(
        "src.content.editorial_jobs.fetch_market_quotes",
        lambda snapshot=False: [
            MarketQuote("BTC", 110000, 1.0),
            MarketQuote("ETH", 2800, -1.0),
        ],
    )
    from datetime import date as date_cls, timedelta, timezone as tz

    today = datetime.now(tz.utc).strftime("%Y-%m-%d")
    week_ago = (date_cls.fromisoformat(today) - timedelta(days=7)).isoformat()
    record_quotes(
        [MarketQuote("BTC", 100000), MarketQuote("ETH", 3000)],
        week_ago,
        path=hist,
    )
    result = post_numbers_that_matter(
        type("P", (), {})(), _numbers_config(), dry_run=True
    )
    assert result["dry_run"] is True
    assert "BTC $110,000 vs $100,000" in result["text"]
    assert "+10.0% over 7 days." in result["text"]
    assert "#bitcoin" in result["text"]


def test_numbers_week_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.content.editorial_jobs.STATE_FILE", tmp_path / "state.json"
    )
    from src.content.editorial_jobs import _save_state

    _save_state(
        {"week": "2099-W01", "numbers": 3, "numbers_day": ""},
        tmp_path / "state.json",
    )
    monkeypatch.setattr(
        "src.content.editorial_jobs._week_key", lambda tz: "2099-W01"
    )
    result = post_numbers_that_matter(
        type("P", (), {})(), _numbers_config(), dry_run=True
    )
    assert result["reason"] == "week_cap"
