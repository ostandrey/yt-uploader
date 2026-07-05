"""Naturalize punctuation for social copy."""

from src.content.naturalize import naturalize_text


def test_naturalize_replaces_em_dash():
    assert naturalize_text("Fed holds rates — Bitcoin drops") == "Fed holds rates - Bitcoin drops"


def test_naturalize_collapses_whitespace():
    assert naturalize_text("  Bitcoin   rises  ") == "Bitcoin rises"
