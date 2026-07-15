#!/usr/bin/env python3
"""
Print tokens/coin_wire_token.json as a single line for Railway
YOUTUBE_CRYPTO_TOKEN_JSON secret.

  python scripts/print_youtube_token_for_railway.py

Then paste the printed JSON into Railway Variables (one line).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = ROOT / "tokens" / "coin_wire_token.json"


def main() -> None:
    if not TOKEN.exists():
        print(f"Missing {TOKEN}. Run: python setup_youtube_oauth.py --force", file=sys.stderr)
        sys.exit(1)
    data = json.loads(TOKEN.read_text(encoding="utf-8"))
    # One line — easy paste into Railway dashboard
    print(json.dumps(data, separators=(",", ":")))


if __name__ == "__main__":
    main()
