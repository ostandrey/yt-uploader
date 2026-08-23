"""Desk items state-machine + retry + scheduler lock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def test_get_desk_items_keeps_open_across_midnight(tmp_path, monkeypatch):
    from src.desk import catalog, db
    from src.desk.items import DESK_QUEUED, DESK_POSTED, get_desk_items

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    monkeypatch.setenv("DESK_TZ", "UTC")
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    now = datetime.now(timezone.utc)
    catalog.write_editorial_items(
        [
            {
                "id": "open-yest",
                "kind": "news",
                "label": "Threads — news",
                "text": "Open from yesterday still needs posting",
                "created_at": (now - timedelta(hours=20)).isoformat(),
                "status": DESK_QUEUED,
            },
            {
                "id": "done-yest",
                "kind": "news",
                "label": "Threads — news",
                "text": "Posted yesterday should be history",
                "created_at": (now - timedelta(hours=20)).isoformat(),
                "status": DESK_POSTED,
            },
            {
                "id": "open-old",
                "kind": "news",
                "label": "Threads — news",
                "text": "Stale open beyond window",
                "created_at": (now - timedelta(hours=40)).isoformat(),
                "status": DESK_QUEUED,
            },
        ]
    )
    today = {row["id"]: row for row in get_desk_items(scope="today", item_type="editorial")}
    history = {row["id"]: row for row in get_desk_items(scope="history", item_type="editorial")}
    assert "open-yest" in today
    assert today["open-yest"]["status"] == DESK_QUEUED
    assert "done-yest" in history
    assert "open-old" in history


def test_push_desk_item_dedup(tmp_path, monkeypatch):
    from src.content import editorial_jobs
    from src.desk import catalog, db

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    monkeypatch.setenv("DESK_TZ", "UTC")
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    monkeypatch.setattr(
        "src.desk.push.notify_desk_push",
        lambda *a, **k: {"reason": "ok", "sent": 1, "subs": 1},
    )
    editorial_jobs._push_desk_item("news", "Threads — news", "Same pack body twice")
    editorial_jobs._push_desk_item("news", "Threads — news", "Same pack body twice")
    items = catalog.load_editorial_items(scope="all")
    assert len(items) == 1
    assert items[0]["status"] == "desk_queued"


def test_with_retry_backoff(monkeypatch):
    from src.ops.retry import with_retry

    sleeps: list[float] = []
    monkeypatch.setattr("src.ops.retry.time.sleep", sleeps.append)
    calls = {"n": 0}

    @with_retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(ValueError,), label="t")
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3
    assert sleeps == [2.0, 4.0]


def test_scheduler_state_clears_running_and_stale(tmp_path, monkeypatch):
    from src.ops import scheduler_state as ss

    monkeypatch.setattr(ss, "STATE_FILE", tmp_path / "scheduler_state.json")
    monkeypatch.setattr(ss, "LOCK_FILE", tmp_path / "scheduler_state.lock")
    ss.mark_job("job_short", "running")
    data = ss.read_state()
    assert data["jobs"]["job_short"]["is_running"] is True
    ss.mark_job("job_short", "failed")
    data = ss.read_state()
    assert data["jobs"]["job_short"]["is_running"] is False
    assert data["jobs"]["job_short"]["status"] == "failed"

    ss.mark_job("job_short", "running")
    # Force stale start time
    raw = ss._load_unlocked()
    started = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    raw["jobs"]["job_short"]["last_started_at"] = started
    ss._write_unlocked(raw)
    data = ss.read_state()
    assert data["jobs"]["job_short"]["is_running"] is False
    assert data["jobs"]["job_short"]["stale"] is True


def test_context_fallback_not_generic_outlet():
    from src.media.ig_carousel import _context_fallback

    text = _context_fallback(
        "BlackRock filed for a Bitcoin ETF with the SEC yesterday.",
        "Flows matter more than the filing date.",
        "Bitcoin ETF filing lands",
    )
    assert "outlet published" not in text.lower()
    assert len(text.split()) >= 12
    assert "BlackRock" in text or "SEC" in text


def test_editorial_skip_and_empty_copy(tmp_path, monkeypatch):
    from src.desk import catalog, db
    from src.desk.items import DESK_SKIPPED

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    monkeypatch.setenv("DESK_TZ", "UTC")
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    catalog.write_editorial_items(
        [
            {
                "id": "skip-me",
                "kind": "news",
                "label": "Threads — news",
                "text": "Skip this pack please",
                "done": False,
            }
        ]
    )
    row = catalog.set_editorial_skipped("skip-me", "operator")
    assert row["status"] == DESK_SKIPPED
    assert row["badge"] == "ПРОПУСК"
    empty = catalog.empty_panel_copy("threads", next_check="Наступна перевірка: ~10 хв")
    assert "Threads" in empty["title"]
    assert "10 хв" in empty["body"]
    stamp = catalog.desk_stamp()
    assert "pack_updated_at" in stamp
    assert "open" in stamp
