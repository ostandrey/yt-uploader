#!/usr/bin/env python3
"""
Generate Coin Wire channel branding assets for YouTube Studio.

Output:
    data/assets/channel/banner_2560x1440.png
    data/assets/channel/profile_800x800.png
    data/assets/channel/watermark_150x150.png
    data/assets/channel/thumbnail_preview.jpg

Upload in YouTube Studio → Customization (Персоналізація):
    - Banner (Банер)
    - Profile picture (Зображення)
    - Video watermark (Водяний знак відео)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.media.thumbnail_generator import (
    create_channel_banner,
    create_channel_profile,
    create_short_thumbnail,
    create_video_watermark,
)

OUT = ROOT / "data" / "assets" / "channel"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    create_channel_banner(OUT / "banner_2560x1440.png", channel_name="Coin Wire")
    create_channel_profile(OUT / "profile_800x800.png")
    create_video_watermark(OUT / "watermark_150x150.png")
    create_short_thumbnail(
        "Spot bitcoin ETFs snap five-day outflow streak with $85.8 million inflow",
        OUT / "thumbnail_preview.jpg",
    )

    print("=" * 60)
    print("Coin Wire — Channel branding assets")
    print("=" * 60)
    for path in sorted(OUT.iterdir()):
        print(f"  {path}")
    print()
    print("Upload these in YouTube Studio -> Personalization:")
    print("  banner_2560x1440.png  -> Banner")
    print("  profile_800x800.png   -> Profile picture")
    print("  watermark_150x150.png -> Video watermark")
    print()
    print("Suggested channel description (copy-paste):")
    print("-" * 60)
    print(
        "Daily crypto market news in under 60 seconds.\n"
        "Bitcoin, Ethereum, ETF flows, Fed policy & breaking headlines.\n\n"
        "New Short every day — unfiltered market moves.\n"
        "Telegram: @coinwirenews\n\n"
        "Not financial advice. News and education only."
    )


if __name__ == "__main__":
    main()
