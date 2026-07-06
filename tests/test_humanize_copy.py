"""Humanize copy helpers."""

from src.content.humanize_copy import (
    humanize_takeaway,
    pick_engagement_question,
    pick_threads_tags,
    strip_ai_filler,
)


def test_strip_ai_filler():
    text = "Bitcoin often move on macro data. This is a developing story."
    out = strip_ai_filler(text)
    assert "developing story" not in out.lower()


def test_humanize_takeaway_one_sentence():
    raw = "BTC often moves with macro. ETH tends to lag when liquidity tightens."
    out = humanize_takeaway(raw)
    assert out.count(".") <= 1
    assert len(out) <= 160


def test_engagement_questions_not_survey_style():
    q = pick_engagement_question("seed-1")
    assert "What's your take" not in q
    assert len(q) < 60


def test_pick_threads_tags_varies():
    a = pick_threads_tags("seed-a")
    b = pick_threads_tags("seed-b")
    assert a.startswith("#")
    # different seeds usually pick different starting tags
    assert a != b or pick_threads_tags("seed-a", count=3) != pick_threads_tags("seed-b", count=3)
