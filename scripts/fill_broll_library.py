#!/usr/bin/env python3
"""
Fill data/assets/broll_library/ from Pexels/Pixabay, then mark clips with QA.

Rejects (tech / YOLO) move to category/_rejected/ and get *.meta.json.

Usage:
  python scripts/fill_broll_library.py --dry-run
  python scripts/fill_broll_library.py --max 10
  python scripts/fill_broll_library.py --no-yolo
  python scripts/fill_broll_library.py --category bitcoin,macro
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.media.broll_fill import FillConfig, fill_broll_library
from src.media.broll_library import VALID_CATEGORIES
from src.media.broll_qa import yolo_available


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-fill B-roll library + YOLO QA")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max", type=int, default=None, help="Max downloads this run")
    parser.add_argument("--no-yolo", action="store_true", help="Skip YOLO (ffprobe only)")
    parser.add_argument(
        "--category",
        type=str,
        default="",
        help="Comma-separated categories (default: all)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    config_path = ROOT / "config" / "coin_wire.yaml"
    config = {}
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    cfg = FillConfig.from_yaml(config)
    if args.max is not None:
        cfg.max_downloads_per_run = args.max
    if args.no_yolo:
        cfg.run_yolo = False
    if args.category.strip():
        wanted = [c.strip() for c in args.category.split(",") if c.strip()]
        bad = [c for c in wanted if c not in VALID_CATEGORIES]
        if bad:
            print(f"Unknown categories: {bad}. Valid: {sorted(VALID_CATEGORIES)}")
            return 2
        cfg.categories = wanted

    if cfg.run_yolo and not yolo_available():
        print(
            "NOTE: ultralytics not installed — ffprobe QA only.\n"
            "  pip install ultralytics opencv-python-headless\n"
        )

    result = fill_broll_library(cfg, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
