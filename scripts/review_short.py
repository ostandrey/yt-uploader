#!/usr/bin/env python3
"""Review a rendered Coin Wire Short (rules + optional vision LLM).

  python scripts/review_short.py --video data/storage/coin_wire/videos/foo.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.media.shorts_qa import review_short


def main() -> None:
    parser = argparse.ArgumentParser(description="QA a Coin Wire Short")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--script", default="")
    args = parser.parse_args()
    video = args.video.expanduser()
    if not video.is_file():
        print(
            f"Video not found: {video}\n"
            "Pass a real MP4, e.g.\n"
            "  python scripts/review_short.py --video data/storage/coin_wire/videos/short_....mp4\n"
            "On Railway: ls /app/data/storage/coin_wire/videos/",
            file=sys.stderr,
        )
        sys.exit(2)
    report = review_short(
        video,
        work_dir=args.work_dir,
        script=args.script,
    )
    print(report.as_telegram())
    print(json.dumps({"score": report.score, "source": report.source}, indent=2))


if __name__ == "__main__":
    main()
