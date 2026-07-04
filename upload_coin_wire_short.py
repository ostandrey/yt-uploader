#!/usr/bin/env python3
"""
Upload Coin Wire Short to YouTube with owner approval flow.

Workflow:
  1. python upload_coin_wire_short.py
     → uploads as UNLISTED (only you see it)
     → Telegram notification with preview link

  2. Watch the unlisted Short, then publish:
     python upload_coin_wire_short.py --publish VIDEO_ID

  Or skip review:
     python upload_coin_wire_short.py --approve

Usage:
    python setup_youtube_oauth.py          # once, first time
    python create_test_short.py            # generate video
    python upload_coin_wire_short.py         # upload unlisted + notify
    python upload_coin_wire_short.py --publish dQw4w9WgXcQ
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.pending_publish import add_pending_upload, mark_published
from src.publishers.telegram_publisher import TelegramPublisher
from src.publishers.youtube_publisher import YouTubePublisher

DEFAULT_VIDEO = ROOT / "data" / "storage" / "coin_wire" / "videos" / "test_short.mp4"
PENDING_FILE = ROOT / "data" / "storage" / "coin_wire" / "pending_uploads.json"

DEFAULT_TITLE = "Fed Holds Rates — Bitcoin Drops 4%"
DEFAULT_DESCRIPTION = """Bitcoin fell 4% after the Fed kept rates unchanged. Ethereum followed lower.

Follow @coinwirenews for daily crypto market moves.

#bitcoin #ethereum #cryptonews #fed #crypto #shorts
"""
DEFAULT_TAGS = [
    "bitcoin", "crypto", "cryptonews", "ethereum", "fed",
    "interestrates", "shorts", "coinwire", "marketnews",
]


def _load_metadata(video_path: Path) -> dict:
    work_dir = video_path.parent.parent / "renders" / video_path.stem
    meta_path = work_dir / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def _save_pending(video_id: str, title: str, privacy: str) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    pending: list = []
    if PENDING_FILE.exists():
        pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    pending.append({
        "video_id": video_id,
        "title": title,
        "privacy": privacy,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    PENDING_FILE.write_text(json.dumps(pending, indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Upload Coin Wire Short to YouTube")
    parser.add_argument(
        "--video",
        type=Path,
        default=DEFAULT_VIDEO,
        help="Path to MP4 file",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Upload as PUBLIC immediately (skip review)",
    )
    parser.add_argument(
        "--publish",
        metavar="VIDEO_ID",
        help="Make an existing unlisted video PUBLIC",
    )
    parser.add_argument(
        "--hold",
        metavar="VIDEO_ID",
        help="Cancel scheduled auto-publish (keep unlisted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without uploading",
    )
    args = parser.parse_args()

    publisher = YouTubePublisher()

    if args.publish:
        video_id = args.publish.strip()
        print(f"Publishing {video_id} as PUBLIC...")
        publisher.set_privacy(video_id, "public")
        mark_published(video_id)
        url = YouTubePublisher.short_url(video_id)
        print(f"Done: {url}")
        try:
            from src.publishers.telegram_publisher import control_keyboard

            TelegramPublisher().notify_owner(
                f"Coin Wire Short is now PUBLIC:\n{url}",
                buttons=control_keyboard(),
            )
        except Exception as exc:
            print(f"Telegram notify failed: {exc}")
        return

    if args.hold:
        from src.publishers.pending_publish import hold_scheduled

        video_id = args.hold.strip()
        if hold_scheduled(video_id):
            print(f"Held {video_id} — auto-publish cancelled, stays unlisted.")
        else:
            print(f"No scheduled entry for {video_id}")
        return

    video_path = args.video.resolve()
    if not video_path.exists():
        print(f"Video not found: {video_path}")
        print("Run: python create_test_short.py")
        sys.exit(1)

    meta = _load_metadata(video_path)
    title = meta.get("title") or args.title
    description = meta.get("description") or args.description
    privacy = "public" if args.approve else "unlisted"

    print("=" * 60)
    print("Coin Wire — YouTube Upload")
    print("=" * 60)
    print(f"Video:   {video_path}")
    print(f"Title:   {title}")
    print(f"Privacy: {privacy}")

    if args.dry_run:
        print("\n[DRY RUN] No upload performed.")
        return

    channel = publisher.get_channel_info()
    print(f"Channel: {channel['title']}")

    video_id = publisher.upload_short(
        video_path=video_path,
        title=title,
        description=description,
        tags=DEFAULT_TAGS,
        privacy_status=privacy,
    )

    url = YouTubePublisher.short_url(video_id)
    studio = YouTubePublisher.studio_url(video_id)
    print(f"\nUploaded: {url}")
    print(f"Studio:   {studio}")

    _save_pending(video_id, title, privacy)

    try:
        from src.publishers.telegram_publisher import control_keyboard

        tg = TelegramPublisher()
        if privacy == "public":
            tg.notify_owner(
                f"Coin Wire Short uploaded (PUBLIC):\n{url}",
                buttons=control_keyboard(),
            )
        else:
            tg.notify_owner(
                "Coin Wire Short ready for review (UNLISTED):\n"
                f"{url}\n\n"
                f"Studio: {studio}",
                buttons=control_keyboard(video_id),
            )
        print("Telegram notification sent.")
    except Exception as exc:
        print(f"Telegram notify failed: {exc}")

    if privacy == "unlisted":
        print("\n--- Approval ---")
        print("1. Open the link above and check the Short")
        print("2. When ready, run:")
        print(f"   python upload_coin_wire_short.py --publish {video_id}")


if __name__ == "__main__":
    main()
