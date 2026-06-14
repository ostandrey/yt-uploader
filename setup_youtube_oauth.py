#!/usr/bin/env python3
"""
One-time YouTube OAuth setup for Coin Wire channel.

1. Fill YOUTUBE_CRYPTO_CLIENT_ID and YOUTUBE_CRYPTO_CLIENT_SECRET in .env
2. Run: python setup_youtube_oauth.py
3. Browser opens — log in with crypto.finance.news.yt@gmail.com
4. Token saved to tokens/coin_wire_token.json (auto-refresh after that)

Prerequisites in Google Cloud Console:
- YouTube Data API v3 enabled
- OAuth consent screen configured (External → add your Gmail as test user)
- OAuth Client ID → Desktop app
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.youtube_publisher import YouTubePublisher


def main() -> None:
    load_dotenv(ROOT / ".env")

    print("=" * 60)
    print("Coin Wire — YouTube OAuth Setup")
    print("=" * 60)

    publisher = YouTubePublisher()
    print("\nOpening browser for Google login...")
    print("Use: crypto.finance.news.yt@gmail.com (your Coin Wire account)\n")

    info = publisher.get_channel_info()
    print("Connected successfully!")
    print(f"  Channel: {info['title']}")
    print(f"  ID:      {info['id']}")
    print(f"  Subs:    {info['subscribers']}")
    print(f"\nToken saved: {publisher.token_file}")
    print("\nNext: python upload_coin_wire_short.py")


if __name__ == "__main__":
    main()
