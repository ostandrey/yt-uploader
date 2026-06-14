#!/usr/bin/env python3
"""Send a test message to Coin Wire Telegram channel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.publishers.telegram_publisher import TelegramPublisher


def main() -> None:
    publisher = TelegramPublisher()
    publisher.post_to_channel(
        "Coin Wire test post.\n\nDaily crypto & market news coming soon.\n\nNot financial advice."
    )
    print("OK — test post sent to channel.")


if __name__ == "__main__":
    main()
