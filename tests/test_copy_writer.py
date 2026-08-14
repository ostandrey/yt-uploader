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
    assert copy.ig_caption
    assert copy.tiktok_caption
    assert copy.tiktok_caption != copy.ig_caption
    assert "Full story on YouTube" in copy.tiktok_caption
    assert copy.carousel_caption
    assert "Not financial advice" not in copy.ig_caption


def test_validate_llm_payload_rejects_hype():
    article = {"title": "Bitcoin ETF inflows rise on Friday"}
    bad = _validate_llm_payload(
        {
            "short_title": "Buy now Bitcoin 100x moon",
            "script_lines": ["a", "b", "c", "d"],
            "ig_caption": "y",
            "carousel_caption": "z",
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
            "ig_caption": "Bitcoin ETF inflows turned positive. Full breakdown on YouTube.\n\n#bitcoin #btc #etf #cryptonews #federalreserve",
            "carousel_caption": "Bitcoin ETF inflows — swipe for the tape.\n\nSwipe for context.\n\nSource: coindesk\n\n#bitcoin #etf #cryptonews #btc",
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
    assert content["ig_caption"]
    assert content["tiktok_caption"]
    assert content["tiktok_caption"] != content["ig_caption"]
    assert content["carousel_caption"]
    assert content.get("copy_source") in ("rules", "llm", "rules_fallback")


def test_llm_failure_tagged_as_rules_fallback(monkeypatch):
    monkeypatch.setenv("COPY_LLM_ENABLED", "1")
    monkeypatch.setenv("COPY_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("src.content.copy_writer._call_llm", lambda _article: None)
    article = {
        "title": "Bitcoin drops 4 percent after Fed holds rates",
        "summary": "Traders cut risk after the Federal Reserve kept rates unchanged.",
        "link": "https://example.com/a",
        "source": "coindesk",
        "hash": "abc123",
    }
    copy = generate_platform_copy(article)
    assert copy.source == "rules_fallback"
