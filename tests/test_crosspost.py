"""Cross-post captions and orchestrator behavior."""

from __future__ import annotations

from pathlib import Path

from src.publishers.captions import (
    build_caption,
    build_threads_text,
    pick_engagement_question,
    should_add_engagement_question,
)
from src.publishers.crosspost import format_crosspost_summary, run_crosspost


def test_build_caption_includes_hashtags_and_disclaimer():
    caption = build_caption("Bitcoin Drops 4%", "Markets reacted to the Fed.")
    assert "Bitcoin Drops 4%" in caption
    assert "#bitcoin" in caption
    assert "Not financial advice" in caption


def test_threads_text_under_500():
    text = build_threads_text(
        "A" * 200,
        "B" * 200,
        youtube_url="https://youtube.com/shorts/abc123XYZ01",
    )
    assert len(text) <= 500


def test_threads_text_can_include_engagement_question():
    text = build_threads_text(
        "Bitcoin drops 4%",
        engagement_question="What's your take?",
    )
    assert "What's your take?" in text
    assert "#bitcoin" in text


def test_engagement_question_is_deterministic():
    assert should_add_engagement_question("same-seed", 0.35) == should_add_engagement_question(
        "same-seed", 0.35
    )
    assert pick_engagement_question("same-seed") == pick_engagement_question("same-seed")


def test_run_crosspost_skips_when_disabled(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 1000)
    out = run_crosspost(
        video,
        "Title",
        config={"publishing": {
            "tiktok": {"enabled": False},
            "instagram": {"enabled": False},
            "threads": {"enabled": False},
        }},
    )
    assert out["results"] == {}
    assert out["errors"] == {}
    assert out["skipped"] == {}


def test_run_crosspost_skips_missing_credentials(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 1000)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "")
    monkeypatch.setenv("META_ACCESS_TOKEN", "")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "")
    monkeypatch.setenv("THREADS_USER_ID", "")
    monkeypatch.setenv("CROSSPOST_S3_BUCKET", "")
    monkeypatch.setattr("src.publishers.tiktok_publisher.load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setattr("src.publishers.instagram_publisher.load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setattr("src.publishers.threads_publisher.load_dotenv", lambda *_a, **_k: None)

    out = run_crosspost(
        video,
        "Title",
        config={"publishing": {
            "tiktok": {"enabled": True},
            "instagram": {"enabled": True, "reel": True, "feed_image": True},
            "threads": {"enabled": True, "mode": "text"},
        }},
    )
    assert "tiktok" in out["skipped"]
    assert "threads" in out["skipped"]
    assert "instagram" in out["skipped"] or "instagram_reel" in out["skipped"]


def test_format_crosspost_summary():
    text = format_crosspost_summary({
        "results": {
            "tiktok": {"status": "PUBLISH_COMPLETE"},
            "instagram_reel": {"url": "https://instagram.com/reel/1", "format": "reel"},
        },
        "skipped": {"instagram_feed": "no host"},
        "errors": {"threads": "boom"},
    })
    assert "OK tiktok" in text
    assert "OK instagram_reel (reel)" in text
    assert "SKIP instagram_feed" in text
    assert "FAIL threads" in text
