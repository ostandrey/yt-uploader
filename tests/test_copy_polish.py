"""Hashtag and copy polish tests."""

from src.content.copy_polish import llm_copy_passes_qa, polish_ig_caption, polish_script_lines
from src.content.voice import copy_contains_banned
from src.publishers.captions import pick_ig_hashtag_tags


def test_copy_contains_banned_phrases():
    assert copy_contains_banned("This underscores the importance of crypto")
    assert copy_contains_banned("Here's what you need to know about ETF")
    assert not copy_contains_banned("BlackRock ETF pulled $4.6B in three days.")


def test_llm_copy_rejects_long_sentences():
    long = " ".join(["word"] * 25) + "."
    assert llm_copy_passes_qa(long) is False
    assert llm_copy_passes_qa("BlackRock ETF pulled $4.6B in three days.")


def test_polish_script_forces_cta():
    script = polish_script_lines(
        [
            "BlackRock ETF pulled $4.6B in three days.",
            "That is the fastest pace since launch.",
            "Total assets are above $58B.",
        ]
    )
    assert script.endswith("Follow Coin Wire for daily crypto news.")


def test_pick_ig_hashtags_five_with_topic():
    text = "Ripple wins partial SEC clarity on XRP sales"
    tags = pick_ig_hashtag_tags(text, 5)
    assert len(tags) == 5
    assert "ripple" in tags


def test_polish_ig_caption_fixes_hashtag_count():
    raw = """$4.6B into BlackRock BTC ETF in three days.
Full breakdown on YouTube.
#bitcoin #crypto #cryptonews #btc #ethereum #sec #etf"""
    out = polish_ig_caption(raw, "BlackRock Bitcoin ETF $4.6B inflows")
    assert out.count("#") == 5
    assert "Full breakdown on YouTube." in out
