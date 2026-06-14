#!/usr/bin/env python3
"""
Create a test YouTube Short for the Coin Wire crypto news channel.

Usage:
    pip install edge-tts imageio-ffmpeg pillow python-dotenv requests
    python create_test_short.py

Output:
    data/storage/coin_wire/videos/test_short.mp4
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.media.ffmpeg_short_renderer import FFmpegShortRenderer


TEST_TITLE = "Fed Holds Rates — Bitcoin Drops 4%"

TEST_SCRIPT = """
Bitcoin dropped four percent after the Fed held rates steady.
Markets expected a hawkish tone, but the Fed kept rates unchanged.
Ethereum followed Bitcoin lower, falling about three percent.
Crypto remains highly sensitive to Federal Reserve policy.
Get the next shift. Follow Coin Wire for daily market moves.
""".strip()


def main() -> None:
    load_dotenv(ROOT / ".env")

    output_path = ROOT / "data" / "storage" / "coin_wire" / "videos" / "test_short.mp4"
    work_dir = ROOT / "data" / "storage" / "coin_wire" / "renders" / "test_short"

    print("=" * 60)
    print("Coin Wire — Test Short Generator")
    print("=" * 60)
    print(f"Title:  {TEST_TITLE}")
    print(f"Output: {output_path}")
    print()

    renderer = FFmpegShortRenderer(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        pixabay_api_key=os.getenv("PIXABAY_API_KEY"),
    )

    renderer.render(
        script=TEST_SCRIPT,
        title=TEST_TITLE,
        output_path=output_path,
        keywords=["bitcoin", "stock market", "federal reserve", "cryptocurrency"],
        voice="en-US-AndrewNeural",
        rate="+5%",
        pitch="-2Hz",
        work_dir=work_dir,
    )

    print()
    print("Next steps:")
    print("  1. Open the MP4 and check voice + subtitles + visuals")
    print("  2. Post news: python post_crypto_news.py --dry-run")
    print("  3. See STRATEGY.md for the full roadmap")


if __name__ == "__main__":
    main()
