#!/usr/bin/env python3
"""Local desk: DESK_PASSWORD=secret python scripts/run_desk.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("DESK_PASSWORD", "").strip():
        raise SystemExit("Set DESK_PASSWORD in .env")
    import uvicorn

    host = os.getenv("DESK_HOST", "127.0.0.1")
    port = int(os.getenv("DESK_PORT") or "8080")
    print(f"Desk http://{host}:{port}/  (Ctrl+C to stop)")
    uvicorn.run("src.desk.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
