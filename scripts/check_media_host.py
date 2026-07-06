#!/usr/bin/env python3
"""Quick check: R2/S3 media host env + optional test upload."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.publishers.media_host import media_host_configured, upload_public_file


def main() -> int:
    required = (
        "CROSSPOST_S3_BUCKET",
        "CROSSPOST_S3_ACCESS_KEY",
        "CROSSPOST_S3_SECRET_KEY",
        "CROSSPOST_S3_PUBLIC_BASE_URL",
        "CROSSPOST_S3_ENDPOINT",
    )
    print("Coin Wire media host check\n")
    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print("Missing env vars:")
        for key in missing:
            print(f"  - {key}")
        return 1

    if not media_host_configured():
        print("media_host_configured() = False (check PUBLIC_BASE_URL)")
        return 1

    print("Env looks complete.")
    if "--upload" not in sys.argv:
        print("Run with --upload to push a 1x1 test JPEG and verify public URL.")
        return 0

    try:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.jpg"
            Image.new("RGB", (64, 64), (0, 255, 136)).save(path, "JPEG")
            url = upload_public_file(path, prefix="coinwire-test")
        print(f"Upload OK: {url}")
        print("Open the URL in a browser to confirm it loads.")
        return 0
    except Exception as exc:
        print(f"Upload FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
