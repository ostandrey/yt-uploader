#!/usr/bin/env python3
"""
Score B-roll library clips with CLIP (category fit). Updates *.meta.json.

Usage:
  python scripts/index_broll_library.py --dry-run --limit 5
  python scripts/index_broll_library.py --category regulation
  python scripts/index_broll_library.py --apply-move   # move if better folder wins by margin
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.media.broll_clip import clip_available, index_one_clip
from src.media.broll_library import DEFAULT_LIBRARY, VALID_CATEGORIES, _is_rejected


def main() -> int:
    parser = argparse.ArgumentParser(description="CLIP-index B-roll library")
    parser.add_argument("--category", default="", help="Comma-separated, or all")
    parser.add_argument("--limit", type=int, default=0, help="Max clips this run (0=all)")
    parser.add_argument("--apply-move", action="store_true", help="Move to suggested category")
    parser.add_argument("--dry-run", action="store_true", help="Score but do not write meta")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not clip_available():
        print("open-clip-torch is required. In .venv run:\n  pip install open-clip-torch")
        return 2

    cats = (
        [c.strip() for c in args.category.split(",") if c.strip()]
        if args.category.strip()
        else sorted(VALID_CATEGORIES)
    )
    bad = [c for c in cats if c not in VALID_CATEGORIES]
    if bad:
        print(f"Unknown categories: {bad}")
        return 2

    work_root = DEFAULT_LIBRARY / "_clip_work"
    done = 0
    suggestions = 0
    results = []

    for cat in cats:
        folder = DEFAULT_LIBRARY / cat
        if not folder.is_dir():
            continue
        for mp4 in sorted(folder.glob("*.mp4")):
            if mp4.stat().st_size < 50_000 or _is_rejected(mp4):
                continue
            if args.limit and done >= args.limit:
                break
            if args.dry_run:
                from src.media.broll_clip import best_category, score_video_categories
                scores = score_video_categories(mp4, work_root / mp4.stem)
                best, best_score, suggest = best_category(scores, current=cat)
                info = {
                    "path": str(mp4),
                    "category": cat,
                    "folder_score": scores.get(cat),
                    "best": best,
                    "best_score": best_score,
                    "suggest_move": suggest,
                    "moved": False,
                }
            else:
                info = index_one_clip(
                    mp4,
                    category=cat,
                    work_root=work_root,
                    apply_move=args.apply_move,
                    library_root=DEFAULT_LIBRARY,
                )
            done += 1
            if info.get("suggest_move"):
                suggestions += 1
            results.append(info)
            logging.info(
                "%s folder=%.3f best=%s(%.3f) move=%s",
                Path(info["path"]).name,
                float(info.get("folder_score") or 0),
                info.get("best"),
                float(info.get("best_score") or 0),
                info.get("suggest_move"),
            )
        if args.limit and done >= args.limit:
            break

    if work_root.exists():
        import shutil
        shutil.rmtree(work_root, ignore_errors=True)

    print(json.dumps({
        "indexed": done,
        "suggestions": suggestions,
        "apply_move": args.apply_move,
        "dry_run": args.dry_run,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
