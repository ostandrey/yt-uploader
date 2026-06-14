#!/usr/bin/env python3
"""
Fetch latest crypto news and post to the Coin Wire Telegram channel.

Usage:
    python post_crypto_news.py
    python post_crypto_news.py --count 3
    python post_crypto_news.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.content.crypto_feeds import CryptoNewsFetcher
from src.publishers.telegram_publisher import TelegramPublisher


def _load_config() -> dict:
    config_path = ROOT / "config" / "coin_wire.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Post crypto news to Telegram")
    parser.add_argument("--count", type=int, default=1, help="Number of posts")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print posts without sending to Telegram",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    config = _load_config()
    fetcher = CryptoNewsFetcher.from_config(config)
    publisher = TelegramPublisher()
    articles = fetcher.fetch_latest(count=args.count, for_short=False)

    if not articles:
        print("No new articles found.")
        return

    print(f"Found {len(articles)} article(s) to post.")

    for index, article in enumerate(articles, start=1):
        post_text = fetcher.format_telegram_post(article)
        print(f"\n--- Post {index}/{len(articles)} ---")
        print(post_text)

        if args.dry_run:
            continue

        publisher.post_to_channel(post_text)
        fetcher.mark_posted(article)
        print("Posted to Telegram channel.")

    if not args.dry_run:
        publisher.notify_owner(
            f"Coin Wire: posted {len(articles)} crypto news update(s) to the channel."
        )


if __name__ == "__main__":
    main()
