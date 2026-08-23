#!/usr/bin/env python3
"""Editorial jobs: weekly Telegram digest, Threads recap, Telegram poll."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.content.editorial_jobs import (
    post_market_snapshot,
    post_numbers_that_matter,
    post_telegram_poll,
    post_threads_recap,
    post_weekly_digest,
)
from src.publishers.telegram_publisher import TelegramPublisher


def _load_config() -> dict:
    with (ROOT / "config" / "coin_wire.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coin Wire editorial jobs")
    parser.add_argument("--weekly-digest", action="store_true")
    parser.add_argument("--threads-recap", action="store_true")
    parser.add_argument("--market-snapshot", action="store_true")
    parser.add_argument("--numbers", action="store_true")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (
        args.weekly_digest
        or args.threads_recap
        or args.poll
        or args.market_snapshot
        or args.numbers
    ):
        parser.error(
            "pick --weekly-digest, --threads-recap, --market-snapshot, --numbers, or --poll"
        )

    load_dotenv(ROOT / ".env")
    config = _load_config()
    publisher = TelegramPublisher()

    if args.weekly_digest:
        result = post_weekly_digest(publisher, config, dry_run=args.dry_run)
        print(result)
    if args.threads_recap:
        result = post_threads_recap(publisher, config, dry_run=args.dry_run)
        print(result)
    if args.market_snapshot:
        result = post_market_snapshot(publisher, config, dry_run=args.dry_run)
        print(result)
    if args.numbers:
        result = post_numbers_that_matter(publisher, config, dry_run=args.dry_run)
        print(result)
    if args.poll:
        result = post_telegram_poll(publisher, config, dry_run=args.dry_run)
        print(result)


if __name__ == "__main__":
    main()
