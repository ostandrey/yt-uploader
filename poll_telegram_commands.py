#!/usr/bin/env python3
"""Poll Telegram for owner bot commands (auto-publish control)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.telegram_bot_commands import poll_commands_once

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    load_dotenv(ROOT / ".env")
    handled = poll_commands_once()
    if handled:
        print(f"Handled {handled} command(s)")


if __name__ == "__main__":
    main()
