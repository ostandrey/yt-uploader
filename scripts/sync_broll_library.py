#!/usr/bin/env python3
"""
Sync B-roll library between PC and Cloudflare R2 / S3.

One-time from your PC (after fill_broll_library):
  python scripts/sync_broll_library.py --upload

Railway worker pulls missing files on start (volume at /app/data):
  python scripts/sync_broll_library.py --download

Dry-run:
  python scripts/sync_broll_library.py --upload --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.media.broll_sync import download_library, sync_configured, upload_library


def main() -> None:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Sync Coin Wire B-roll library ↔ R2/S3")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--upload", action="store_true", help="PC → S3 (run once locally)")
    group.add_argument("--download", action="store_true", help="S3 → disk (Railway / restore)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not sync_configured():
        print(
            "Missing S3 credentials. Set CROSSPOST_S3_BUCKET, "
            "CROSSPOST_S3_ACCESS_KEY, CROSSPOST_S3_SECRET_KEY, CROSSPOST_S3_ENDPOINT "
            "(same R2 bucket as Instagram is fine)."
        )
        sys.exit(1)

    if args.upload:
        result = upload_library(dry_run=args.dry_run)
    else:
        result = download_library(dry_run=args.dry_run)

    print(result)
    mb = round(result.get("bytes", 0) / 1e6, 1)
    action = result["action"]
    print(f"Done {action}: transferred≈{mb} MB (dry_run={args.dry_run})")


if __name__ == "__main__":
    main()
