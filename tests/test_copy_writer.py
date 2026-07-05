"""LLM copy writer with rules fallback."""

from __future__ import annotations

from src.content.copy_writer import (
    PlatformCopy,
    generate_content,
    generate_platform_copy,
    llm_configured,
    _rules_copy,
    _validate_llm_payload,
)


def test_llm_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("COPY_LLM_API_KEY", raising=False)
    monkeypatch.setenv("COPY_LLM_ENABLED", "0")
    assert llm_configured() is False


def test_rules_copy_from_article():
    article = {
        "title": "Bitcoin drops 4 percent after Fed holds rates",
        "summary": "Traders cut risk after the Federal Reserve kept rates unchanged.",
        "link": "https://example.com/a",
        "source": "coindesk",
        "hash": "abc123",
    }
    copy = _rules_copy(article, seed="abc123")
    assert copy.source == "rules"
    assert "Bitcoin" in copy.short_title or "bitcoin" in copy.short_title.lower()
    assert len(copy.script.split("\n")) >= 4
    assert len(copy.threads_text) <= 500


def test_validate_llm_payload_rejects_hype():
    article = {"title": "Bitcoin ETF inflows rise on Friday"}
    bad = _validate_llm_payload(
        {
            "short_title": "Buy now Bitcoin 100x moon",
            "script_lines": ["a", "b", "c", "d"],
            "threads_text": "x",
            "threads_question": "",
            "ig_caption": "y",
        },
        article,
    )
    assert bad is None


def test_validate_llm_payload_accepts_clean_json():
    article = {"title": "Bitcoin ETF inflows rise on Friday session"}
    good = _validate_llm_payload(
        {
            "short_title": "Bitcoin ETF inflows rise on Friday",
            "script_lines": [
                "Spot Bitcoin ETFs pulled in fresh inflows on Friday.",
                "Issuers reported net buying after a five-day outflow streak.",
                "Traders are watching whether inflows can hold into next week.",
                "Fed policy is still the macro backdrop for risk assets.",
                "Follow Coin Wire for the next market shift.",
            ],
            "threads_text": "Bitcoin ETF inflows turned positive on Friday.",
            "threads_question": "Bullish or bearish from here?",
            "ig_caption": "Bitcoin ETF inflows turned positive. #bitcoin #crypto #coinwire",
        },
        article,
    )
    assert good is not None
    assert good.source == "llm"
    assert "ETF" in good.short_title or "Bitcoin" in good.short_title


def test_generate_content_merges_metadata():
    article = {
        "title": "Ethereum network upgrade scheduled for next month",
        "summary": "Developers confirmed the timeline after client releases.",
        "link": "https://example.com/eth",
        "source": "cointelegraph",
        "hash": "eth1",
    }
    content = generate_content(article)
    assert content["source_link"] == "https://example.com/eth"
    assert content["threads_text"]
    assert content["ig_caption"]
    assert content.get("copy_source") in ("rules", "llm")
