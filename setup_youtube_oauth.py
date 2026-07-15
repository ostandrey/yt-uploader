#!/usr/bin/env python3
"""
One-time YouTube OAuth setup for Coin Wire channel.

1. Fill YOUTUBE_CRYPTO_CLIENT_ID and YOUTUBE_CRYPTO_CLIENT_SECRET in .env
2. Run: python setup_youtube_oauth.py
3. Browser opens — log in with crypto.finance.news.yt@gmail.com
4. Token saved to tokens/coin_wire_token.json (auto-refresh after that)

If you get invalid_grant:
  python setup_youtube_oauth.py --force

Prerequisites in Google Cloud Console:
- YouTube Data API v3 enabled
- OAuth consent screen configured (External → add your Gmail as test user)
- OAuth Client ID → Desktop app
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.youtube_publisher import YouTubePublisher


def main() -> None:
    parser = argparse.ArgumentParser(description="Coin Wire YouTube OAuth")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing token and open browser login again",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    print("=" * 60)
    print("Coin Wire — YouTube OAuth Setup")
    print("=" * 60)

    publisher = YouTubePublisher()
    print("\nOpening browser for Google login...")
    print("Use: crypto.finance.news.yt@gmail.com (your Coin Wire account)\n")

    # Force new login when asked, or when refresh fails inside _load_credentials
    publisher._load_credentials(force_login=args.force)
    publisher._service = None

    info = publisher.get_channel_info()
    print("Connected successfully!")
    print(f"  Channel: {info['title']}")
    print(f"  ID:      {info['id']}")
    print(f"  Subs:    {info['subscribers']}")
    print(f"\nToken saved: {publisher.token_file}")
    print("\nNext: python upload_coin_wire_short.py <video.mp4>")
    print(
        "If Railway uses YOUTUBE_CRYPTO_TOKEN_JSON — paste the new "
        "tokens/coin_wire_token.json contents into that secret."
    )


if __name__ == "__main__":
    main()
