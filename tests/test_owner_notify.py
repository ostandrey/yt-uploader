"""Owner Telegram notice formatting."""

from src.publishers.owner_notify import (
    format_desk_editorial_ready,
    format_short_status_bundle,
    format_tg_channel_status,
    format_threads_pulse_posted,
    format_youtube_status,
)


def test_channel_status_compact():
    text = format_tg_channel_status(
        tier="breaking",
        title="Bitcoin slips toward $64,000 as traders await Wednesday's inflation test",
        score=24,
        post_count=8,
        max_posts=8,
    )
    assert "📢 TG channel" in text
    assert "BREAKING" in text
    assert "24" in text
    assert "8/8" in text
    assert "Bitcoin slips" in text
    assert "Coin Wire TG:" not in text


def test_short_status_bundle():
    text = format_short_status_bundle(
        title="BlackRock ETF inflows",
        desk_url="https://desk.example",
        qa_score=71,
        youtube_url="https://youtu.be/x",
        youtube_state="unlisted",
        publish_hint="public ~30m",
        carousel_slides=6,
    )
    assert "📺 YouTube" in text
    assert "QA 71" in text
    assert "📱 TikTok" in text
    assert "📸 IG Reel" in text
    assert "6 slides" in text
    assert "BlackRock" in text
    assert "https://desk.example/" in text
    assert "https://youtu.be/x" in text


def test_editorial_desk_ready():
    text = format_desk_editorial_ready(kind="opinion", title="ETF flows hit record")
    assert "Threads" in text
    assert "opinion" in text
    assert "desk ready" in text
    assert "ETF flows" in text


def test_threads_pulse_posted():
    text = format_threads_pulse_posted(variant="news_flash", url="https://threads.net/x")
    assert "🧵 Threads" in text
    assert "news flash posted" in text
    assert "https://threads.net/x" in text


def test_youtube_public_status():
    text = format_youtube_status(state="public", url="https://youtu.be/x", publish_hint="My title")
    assert "📺 YouTube · public" in text
    assert "https://youtu.be/x" in text
