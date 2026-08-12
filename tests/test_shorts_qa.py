from src.content.short_script_generator import (
    _summary_sentences,
    _truncate_at_words,
    is_complete_clause,
)
from src.media.shorts_qa import _score_rules
from src.publishers.captions import build_phone_repost_caption, phone_copy_packs


def test_truncate_does_not_end_on_dangling_preposition():
    text = (
        "Binance set records for net BTC outflows on Tuesday, adding to an "
        "emerging trend of positive inflows to"
    )
    out = _truncate_at_words(text, 80, end=".")
    assert out == "" or is_complete_clause(out)
    assert not out.endswith("to.")


def test_summary_sentences_skip_incomplete_stumps():
    summary = (
        "Spot Bitcoin ETFs snapped a five-day outflow streak with fresh inflows Friday. "
        "Binance set multimonth records for net BTC outflows on Tuesday, adding to an "
        "emerging trend of positive inflows to"
    )
    lines = _summary_sentences(summary, max_count=2)
    assert lines
    assert all(is_complete_clause(line) for line in lines)


def test_score_rules_penalizes_long_outro_and_charts():
    score, findings = _score_rules(
        {
            "duration_sec": 45,
            "sentences": 7,
            "outro_sec": 3.0,
            "stat_overlays": [],
            "broll_sources": {"chart": 4, "local": 0},
            "broll_segments": 4,
        },
        "Traders are reacting to the news.\nMarkets are watching the Fed.",
    )
    assert score < 70
    codes = {item.code: item.severity for item in findings}
    assert codes["duration"] in {"warn", "fail"}
    assert codes["outro"] == "fail"


def test_phone_repost_caption_has_platforms():
    text = build_phone_repost_caption("Bitcoin ETF inflows hit $1B", youtube_url="https://youtu.be/x")
    assert "TikTok" in text
    assert "https://youtu.be/x" in text


def test_phone_copy_packs_bodies_are_plain():
    packs = phone_copy_packs("Bitcoin ETF inflows hit $1B", youtube_url="https://youtu.be/x")
    assert len(packs) >= 1
    tiktok_hint, tiktok_body = packs[0]
    assert "TikTok" in tiktok_hint
    assert "long-press" not in tiktok_body.lower()
    assert all("Threads" not in hint for hint, _body in packs)
