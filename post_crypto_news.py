#!/usr/bin/env python3
"""
Fetch crypto news and post to the Coin Wire Telegram channel.

Smart mode (default for worker): 3–8 posts/day — breaking news ASAP,
strong stories when cooldown allows, floor slots guarantee minimum.

Usage:
    python post_crypto_news.py --smart
    python post_crypto_news.py --smart --dry-run
    python post_crypto_news.py --count 1          # legacy batch mode
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
from src.content.telegram_posting import TelegramPostingConfig, run_smart_post
from src.publishers.telegram_publisher import TelegramPublisher
from src.publishers.threads_pulse import ThreadsPulseConfig, maybe_post_news_pulse


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
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Legacy: post N articles in one run (--count)",
    )
    parser.add_argument("--count", type=int, default=1, help="Batch mode: number of posts")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = _load_config()
    fetcher = CryptoNewsFetcher.from_config(config)
    publisher = TelegramPublisher()

    if not args.batch:
        cfg = TelegramPostingConfig.from_config(config)
        result = run_smart_post(fetcher, publisher, cfg, dry_run=args.dry_run)

        if result.get("dry_run"):
            print(f"[DRY RUN] Would post ({result['reason']}) tier={result['tier']} score={result['score']}")
            print(f"Title: {result['title']}\n")
            print(result["text"])
            pulse_cfg = ThreadsPulseConfig.from_config(config)
            pulse = maybe_post_news_pulse(
                result["article"],
                result["tier"],
                pulse_cfg,
                dry_run=True,
            )
            if pulse.get("dry_run"):
                print(f"\n[DRY RUN] Threads pulse ({pulse.get('variant')}):")
                print(pulse.get("text", ""))
            elif pulse.get("reason"):
                print(f"\nThreads pulse skip: {pulse['reason']}")
            return

        if result.get("posted"):
            print(
                f"Posted ({result['reason']}): tier={result['tier']} "
                f"score={result['score']} — {result['title'][:60]}"
            )
            print(f"Today: {result['post_count']} post(s)")

            pulse_cfg = ThreadsPulseConfig.from_config(config)
            pulse = maybe_post_news_pulse(
                result["article"],
                result["tier"],
                pulse_cfg,
            )
            if pulse.get("posted"):
                print(f"Threads pulse ({pulse.get('variant')}): {pulse.get('url')}")
            elif pulse.get("reason"):
                print(f"Threads pulse skip: {pulse['reason']}")

            if not args.dry_run:
                from src.publishers.telegram_publisher import control_keyboard

                publisher.notify_owner(
                    f"Coin Wire TG: {result['tier']} post ({result['score']})\n"
                    f"{result['title'][:80]}\n"
                    f"Today: {result['post_count']}/day",
                    buttons=control_keyboard(),
                )
        else:
            print(
                f"No post ({result['reason']}) — today {result['post_count']}, "
                f"best score {result.get('best_score')}"
            )
        return

    articles = fetcher.fetch_latest(count=args.count, for_short=False)
    if not articles:
        print("No new articles found.")
        return

    print(f"Found {len(articles)} article(s) to post.")
    for index, article in enumerate(articles, start=1):
        from src.content.market_ticker import fetch_market_ticker_line
        from src.content.news_filter import classify_telegram_tier, format_telegram_post_html

        tier = classify_telegram_tier(
            int(article.get("score", 0)),
            insight_score=18,
        )
        post_text = format_telegram_post_html(
            article,
            tier=tier,
            market_line=fetch_market_ticker_line(),
            include_insight=int(article.get("score", 0)) >= 18,
        )
        print(f"\n--- Post {index}/{len(articles)} ---")
        print(post_text)

        if args.dry_run:
            continue

        publisher.post_to_channel_html(
            post_text,
            buttons=[{"text": "Read full story", "url": article["link"]}],
        )
        fetcher.mark_posted(article)
        print("Posted to Telegram channel.")

    if not args.dry_run:
        from src.publishers.telegram_publisher import control_keyboard

        publisher.notify_owner(
            f"Coin Wire: posted {len(articles)} crypto news update(s) to the channel.",
            buttons=control_keyboard(),
        )


if __name__ == "__main__":
    main()
