#!/usr/bin/env python3
"""Post a one-off test thread (verify THREADS_* credentials)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.publishers.threads_publisher import ThreadsPublisher


def main() -> int:
    parser = argparse.ArgumentParser(description="Post a test thread via API")
    parser.add_argument(
        "--text",
        default=(
            "Coin Wire API test. Automated English crypto news is live.\n\n"
            "#bitcoin #crypto #coinwire"
        ),
        help="Thread text (max 500 chars)",
    )
    args = parser.parse_args()

    publisher = ThreadsPublisher()
    if not publisher.configured():
        print("Threads not configured. Set THREADS_ACCESS_TOKEN and THREADS_USER_ID.")
        return 1

    try:
        result = publisher.publish_text(args.text[:500])
        print(f"OK: {result.get('url')}")
        return 0
    except Exception as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
