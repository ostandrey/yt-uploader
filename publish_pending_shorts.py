#!/usr/bin/env python3
"""
Publish scheduled YouTube Shorts after the processing delay.

Worker calls this every few minutes. Manual controls:

  python publish_pending_shorts.py              # publish due videos
  python publish_pending_shorts.py --dry-run    # preview
  python publish_pending_shorts.py --hold ID    # cancel auto-publish for one video

Kill switch: YOUTUBE_AUTO_PUBLISH=0 on Railway (or in .env)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.pending_publish import (
    auto_publish_delay_minutes,
    auto_publish_enabled,
    due_for_publish,
    hold_scheduled,
    publish_due_shorts,
)


def main() -> None:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Auto-publish scheduled Coin Wire Shorts")
    parser.add_argument("--dry-run", action="store_true", help="Show due videos only")
    parser.add_argument("--hold", metavar="VIDEO_ID", help="Cancel scheduled auto-publish")
    args = parser.parse_args()

    if args.hold:
        video_id = args.hold.strip()
        if hold_scheduled(video_id):
            print(f"Held {video_id} — will stay unlisted.")
        else:
            print(f"No scheduled entry found for {video_id}")
        return

    enabled = auto_publish_enabled()
    delay = auto_publish_delay_minutes()
    print(f"Auto-publish: {'ON' if enabled else 'OFF'} (delay {delay} min)")

    if not enabled:
        print("Disabled. Set YOUTUBE_AUTO_PUBLISH=1 or enable in coin_wire.yaml")
        return

    due = due_for_publish()
    if not due:
        print("Nothing due for publish.")
        return

    print(f"Due: {len(due)} video(s)")
    for entry in due:
        print(f"  - {entry['video_id']}: {entry.get('title', '')[:60]}")

    if args.dry_run:
        return

    published = publish_due_shorts()
    for item in published:
        print(f"Published: {item['url']}")


if __name__ == "__main__":
    main()
