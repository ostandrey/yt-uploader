#!/usr/bin/env python3
"""
Full Coin Wire automation — news → Short → YouTube (unlisted) → Telegram approval.

Workflow:
  1. Pick best fresh RSS article
  2. Generate script + render Short
  3. Upload as UNLISTED (if OAuth configured)
  4. Notify you in Telegram with preview link + publish command

Usage:
    python setup_youtube_oauth.py          # once
    python run_coin_wire_pipeline.py       # full run
    python run_coin_wire_pipeline.py --skip-upload   # video only
    python run_coin_wire_pipeline.py --post-telegram # also post news to channel
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.content.copy_writer import generate_content
from src.content.crypto_feeds import CryptoNewsFetcher
from src.media.ffmpeg_short_renderer import FFmpegShortRenderer
from src.publishers.pending_publish import (
    add_pending_upload,
    auto_publish_delay_minutes,
    auto_publish_enabled,
)
from src.publishers.crosspost import format_crosspost_summary, run_crosspost
from src.publishers.telegram_publisher import TelegramPublisher, control_keyboard
from src.publishers.youtube_publisher import YouTubePublisher

VIDEOS_DIR = ROOT / "data" / "storage" / "coin_wire" / "videos"
USED_SHORTS_FILE = ROOT / "data" / "storage" / "coin_wire" / "used_short_articles.json"

DEFAULT_TAGS = [
    "bitcoin", "crypto", "cryptonews", "ethereum", "fed",
    "interestrates", "shorts", "coinwire", "marketnews",
]


def _load_config() -> dict:
    config_path = ROOT / "config" / "coin_wire.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_used_short_hashes() -> set[str]:
    if not USED_SHORTS_FILE.exists():
        return set()
    try:
        data = json.loads(USED_SHORTS_FILE.read_text(encoding="utf-8"))
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_used_short_hash(article_hash: str) -> None:
    USED_SHORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    used = _load_used_short_hashes()
    used.add(article_hash)
    trimmed = list(used)[-200:]
    payload = {"hashes": trimmed, "updated": datetime.now(timezone.utc).isoformat()}
    USED_SHORTS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save_pending(video_id: str, title: str, *, config: dict) -> dict:
    schedule = auto_publish_enabled(config)
    delay = auto_publish_delay_minutes(config)
    return add_pending_upload(
        video_id,
        title,
        schedule_auto_publish=schedule,
        delay_minutes=delay,
    )


def _pick_article(fetcher: CryptoNewsFetcher) -> dict | None:
    used = _load_used_short_hashes()
    article = fetcher.fetch_best_for_short(skip_hashes=used)
    if article:
        print(f"      Auto-score: {article['score']} — {article['title'][:60]}")
    return article


def _output_paths(slug: str) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    base = f"short_{stamp}_{slug[:30]}"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    video_path = VIDEOS_DIR / f"{safe}.mp4"
    work_dir = ROOT / "data" / "storage" / "coin_wire" / "renders" / safe
    return video_path, work_dir


def _slug_from_title(title: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in title)[:40].strip("_")


def _youtube_ready() -> bool:
    client_id = os.getenv("YOUTUBE_CRYPTO_CLIENT_ID", "")
    client_secret = os.getenv("YOUTUBE_CRYPTO_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return False
    if "your_" in client_id or "your_" in client_secret:
        return False
    token = ROOT / "tokens" / "coin_wire_token.json"
    return token.exists()


def run_pipeline(
    *,
    skip_upload: bool = False,
    post_telegram: bool = False,
    dry_run: bool = False,
) -> dict:
    load_dotenv(ROOT / ".env")
    config = _load_config()
    settings = config.get("settings", {})

    fetcher = CryptoNewsFetcher.from_config(config)
    article = _pick_article(fetcher)
    if not article:
        raise RuntimeError(
            "No serious fresh articles for a Short "
            f"(min score {fetcher.short_min_score}, max age {fetcher.short_max_age_hours}h)."
        )

    content = generate_content(article)

    print("=" * 60)
    print("Coin Wire — Daily Pipeline")
    print("=" * 60)
    print(f"Article: {article['title'][:70]}")
    print(f"Short:   {content['title']}")
    print(f"Copy:    {content.get('copy_source', 'rules')}")
    print()

    if dry_run:
        print("--- Script ---")
        print(content["script"])
        print("\n[DRY RUN] Stopped before render.")
        return {"status": "dry_run", "content": content}

    slug = _slug_from_title(content["title"])
    video_path, work_dir = _output_paths(slug)

    visual_source = settings.get("visual_source", "mixed")
    visual_mode = visual_source
    if visual_mode == "stock_video":
        visual_mode = "stock"

    renderer = FFmpegShortRenderer(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        pixabay_api_key=os.getenv("PIXABAY_API_KEY"),
        visual_mode=visual_mode,
    )
    renderer.render(
        script=content["script"],
        title=content["title"],
        output_path=video_path,
        keywords=content["keywords"],
        voice=settings.get("voice", "en-US-ChristopherNeural"),
        rate=settings.get("voice_rate", "-8%"),
        pitch="-2Hz",
        work_dir=work_dir,
        price_overlay=settings.get("price_overlay", True),
    )

    meta_path = work_dir / "metadata.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["description"] = content["description"]
    meta["source_link"] = content["source_link"]
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    thumb_path = Path(meta.get("thumbnail", ""))

    result = {
        "status": "rendered",
        "video_path": str(video_path),
        "title": content["title"],
        "article_hash": article["hash"],
        "thumbnail_path": str(thumb_path) if thumb_path.exists() else "",
    }

    if post_telegram:
        publisher = TelegramPublisher()
        post_text = fetcher.format_telegram_post(article)
        publisher.post_to_channel(post_text)
        fetcher.mark_posted(article)
        result["telegram_posted"] = True

    if skip_upload:
        _save_used_short_hash(article["hash"])
        try:
            TelegramPublisher().notify_owner(
                "Coin Wire Short rendered (upload skipped):\n"
                f"{video_path}\n\n"
                f"Title: {content['title']}",
                buttons=control_keyboard(),
            )
        except Exception as exc:
            print(f"Telegram notify failed: {exc}")
        return result

    youtube_url = ""
    video_id = ""
    studio = ""
    pending_entry: dict = {}
    auto_on = False
    delay = 30

    if not _youtube_ready():
        print("YouTube OAuth not ready — skipping YouTube upload.")
        result["status"] = "rendered_no_youtube"
    else:
        publisher = YouTubePublisher()
        channel = publisher.get_channel_info()
        print(f"Channel: {channel['title']}")

        video_id = publisher.upload_short(
            video_path=video_path,
            title=content["title"],
            description=content["description"],
            tags=DEFAULT_TAGS,
            privacy_status="unlisted",
        )

        if thumb_path.exists():
            if publisher.set_thumbnail(video_id, thumb_path):
                print(f"Thumbnail uploaded: {thumb_path}")
            else:
                print(
                    "Thumbnail saved locally - upload manually after "
                    "YouTube phone verification (Advanced features)."
                )

        youtube_url = YouTubePublisher.short_url(video_id)
        studio = YouTubePublisher.studio_url(video_id)
        pending_entry = _save_pending(video_id, content["title"], config=config)
        auto_on = auto_publish_enabled(config)
        delay = auto_publish_delay_minutes(config)
        result.update({
            "status": "uploaded",
            "video_id": video_id,
            "url": youtube_url,
            "auto_publish": auto_on,
        })
        print(f"\nUploaded (unlisted): {youtube_url}")
        if auto_on:
            print(f"Auto-publish in ~{delay} min (disable: YOUTUBE_AUTO_PUBLISH=0)")

    # TikTok / Instagram / Threads (independent of YouTube)
    print("\n[crosspost] Starting TikTok / Instagram / Threads...")
    crosspost = run_crosspost(
        video_path,
        content["title"],
        content["description"],
        config=config,
        youtube_url=youtube_url,
        thumbnail_path=thumb_path if thumb_path.exists() else None,
        keywords=content.get("keywords"),
        seed=article["hash"],
        threads_text_override=content.get("threads_text", ""),
        ig_caption_override=content.get("ig_caption", ""),
    )
    result["crosspost"] = crosspost
    print(format_crosspost_summary(crosspost))

    _save_used_short_hash(article["hash"])

    try:
        tg = TelegramPublisher()
        lines = [f"Title: {content['title']}"]
        if youtube_url:
            if pending_entry.get("status") == "scheduled":
                publish_at = pending_entry.get("publish_at", "")[:16].replace("T", " ")
                lines.insert(
                    0,
                    "Coin Wire Short uploaded (UNLISTED, auto-publish scheduled):",
                )
                lines.append(youtube_url)
                lines.append(
                    f"Goes PUBLIC ~{delay} min after upload (~{publish_at} UTC)"
                )
                lines.append(f"Studio: {studio}")
            else:
                lines.insert(0, "Coin Wire Short ready for review (UNLISTED):")
                lines.append(youtube_url)
                lines.append(f"Studio: {studio}")
        else:
            lines.insert(0, "Coin Wire Short rendered (YouTube not configured):")
            lines.append(str(video_path))
        lines.append("")
        lines.append(format_crosspost_summary(crosspost))
        tg.notify_owner(
            "\n".join(lines),
            buttons=control_keyboard(video_id or None),
        )
    except Exception as exc:
        print(f"Telegram notify failed: {exc}")

    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Coin Wire full automation pipeline")
    parser.add_argument("--skip-upload", action="store_true", help="Render only")
    parser.add_argument(
        "--post-telegram",
        action="store_true",
        help="Also post source article to @coinwirenews",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show script only")
    args = parser.parse_args()

    try:
        run_pipeline(
            skip_upload=args.skip_upload,
            post_telegram=args.post_telegram,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Pipeline failed: {exc}")
        try:
            from src.publishers.telegram_publisher import control_keyboard

            TelegramPublisher().notify_owner(
                f"Coin Wire pipeline FAILED:\n{exc}",
                buttons=control_keyboard(),
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
