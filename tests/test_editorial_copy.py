"""Rules fallbacks for editorial copy (no LLM)."""

import re

from src.content.editorial_copy import (
    news_flash,
    opinion_hook,
    question_post,
    telegram_context,
    telegram_poll,
    telegram_weekly_digest,
    weekly_recap,
    weekly_reflection,
)
from src.content.editorial_log import append_event, events_since, format_events_list
from src.content.copy_guard import display_title, looks_like_filename_slug, safe_caption


ARTICLE = {
    "title": "BlackRock Bitcoin ETF inflows hit $4.6B in three days",
    "summary": "Issuers reported the fastest pace since launch as Treasury yields dipped.",
    "hash": "abc123",
    "tier": "strong",
}


def test_copy_guard_rejects_slug():
    slug = "short 20260811 2200 bitcoin stuck as etf inflows o"
    assert looks_like_filename_slug(slug)
    assert looks_like_filename_slug("short_20260811_2200_bitcoin_stuck")
    assert safe_caption(slug, "") == ""
    assert safe_caption(slug, "BlackRock ETF inflows stall") == "BlackRock ETF inflows stall"
    assert display_title(slug) == "Short готовий"


def test_news_flash_and_opinion_are_short(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    flash = news_flash(ARTICLE)
    hook = opinion_hook(ARTICLE)
    assert "BlackRock" in flash
    assert len(flash) <= 500
    assert len(hook) <= 240
    assert "?" not in hook


def test_question_and_context(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    q = question_post(ARTICLE)
    ctx = telegram_context({**ARTICLE, "tier": "breaking"})
    assert "?" in q
    assert "Does this change the setup" not in q
    assert "what happens next" not in q.lower()
    assert re.search(r"which|who is|actually", q, re.I)
    assert "BlackRock" in q or "ETF" in q or "$4.6" in q
    assert len([ln for ln in q.splitlines() if ln.strip()]) <= 2
    assert "Context" in ctx or "context" in ctx.lower()
    assert "Issuers reported the fastest pace" not in ctx
    assert ARTICLE["title"] not in ctx
    assert "—" not in ctx
    assert "—" not in q


def test_weekly_formats(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    events = "— BTC held $68K\n— BlackRock ETF: $4.6B inflows\n— SEC delayed ETH ETF"
    recap = weekly_recap(events)
    digest = telegram_weekly_digest(events)
    assert recap.startswith("This week in crypto:")
    assert "Week in review" in digest or "📋" in digest
    assert "BlackRock" in digest
    assert "—" not in recap
    assert "—" not in digest


def test_weekly_reflection_fallback(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    text = weekly_reflection(
        "BlackRock",
        "BlackRock Bitcoin ETFs pulled in $4.6B over three days",
        "CFTC",
        "The CFTC set Aug. 20 for a committee meeting on crypto, AI, and prediction markets",
    )
    assert "BlackRock" in text or "$4.6" in text
    assert "CFTC" in text
    assert re.search(r"\b(but|still|yet|meanwhile)\b", text, re.I)
    assert re.search(r"\b(mattered|noise|procedural|moved|tape|print|calendar|outcome)\b", text, re.I)
    assert len(text) <= 700
    assert "#" not in text
    assert "?" not in text
    assert "📊" not in text
    sentences = [ln for ln in re.split(r"(?<=[.!?])\s+", text.strip()) if ln.strip()]
    assert 5 <= len(sentences) <= 6


def test_weekly_reflection_rejects_overlap(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    banned = [
        "BlackRock Bitcoin ETFs pulled in $4.6B over three days. That was the week's hard number for BlackRock."
    ]
    text = weekly_reflection(
        "BlackRock",
        "BlackRock Bitcoin ETFs pulled in $4.6B over three days",
        "CFTC",
        "The CFTC set Aug. 20 for a committee meeting on crypto",
        banned=banned,
    )
    assert text
    assert "but" in text.lower() or "still" in text.lower() or "yet" in text.lower()


def test_poll_has_three_options(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    poll = telegram_poll(ARTICLE)
    assert poll is not None
    assert len(poll["options"]) == 3
    assert len(poll["question"]) <= 100


def test_editorial_log_roundtrip(tmp_path):
    path = tmp_path / "log.json"
    append_event(kind="telegram", title="Fed holds rates", path=path)
    append_event(kind="short", title="Bitcoin ETF inflows", path=path)
    items = events_since(7, path=path)
    assert len(items) == 2
    text = format_events_list(items)
    assert "Fed holds rates" in text
