"""Tests for B-roll query planning and local library."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.media.broll_library import normalize_category, pick_local_clip
from src.media.script_parser import (
    PEXELS_QUERIES,
    plan_broll_segments,
    sentence_broll_terms,
    sentence_search_keywords,
    token_category,
)


def test_pexels_queries_are_multi_variant():
    for token, variants in PEXELS_QUERIES.items():
        assert isinstance(variants, list), token
        assert len(variants) >= 2, token
        assert all(isinstance(v, str) and v for v in variants), token


def test_sentence_broll_terms_includes_category():
    terms = sentence_broll_terms("Bitcoin dropped after the Fed raised rates.")
    assert 1 <= len(terms) <= 3
    categories = {t.category for t in terms}
    assert "bitcoin" in categories or "macro" in categories
    for term in terms:
        assert term.query
        assert term.category in {
            "bitcoin", "ethereum", "macro", "regulation", "security", "defi", "default",
        }


def test_sentence_search_keywords_returns_queries():
    sentence = "Ethereum DeFi hack raises security concerns."
    keywords = sentence_search_keywords(sentence)
    assert 1 <= len(keywords) <= 3
    assert all(isinstance(k, str) and k for k in keywords)


def test_token_category_mapping():
    assert token_category("btc") == "bitcoin"
    assert token_category("fed") == "macro"
    assert token_category("hack") == "security"
    assert token_category("defi") == "defi"


def test_plan_broll_segments_has_category():
    segments = plan_broll_segments(
        ["Bitcoin fell sharply today."],
        [6.0],
    )
    assert len(segments) >= 2
    for seg in segments:
        assert "keyword" in seg
        assert "category" in seg
        assert seg["category"] == "bitcoin"


def test_pick_local_clip_from_tmp_library(tmp_path: Path):
    cat_dir = tmp_path / "bitcoin"
    cat_dir.mkdir()
    clip = cat_dir / "btc_01.mp4"
    clip.write_bytes(b"\x00" * 60_000)

    picked = pick_local_clip("bitcoin", set(), tmp_path)
    assert picked == clip


def test_normalize_category_aliases():
    assert normalize_category("btc") == "bitcoin"
    assert normalize_category("fed") == "macro"
    assert normalize_category("unknown_token") == "default"
