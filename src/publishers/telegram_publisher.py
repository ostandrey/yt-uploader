"""
Telegram publisher for Coin Wire channel and personal notifications.
"""

from __future__ import annotations

import os
from typing import Optional

import requests
from dotenv import load_dotenv


class TelegramPublisher:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
        notify_chat_id: Optional[str] = None,
    ):
        load_dotenv()
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")
        self.notify_chat_id = notify_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

    def _send(self, chat_id: str, text: str, disable_preview: bool = False) -> dict:
        if not self.bot_token or not chat_id:
            raise ValueError("Telegram bot token or chat id is missing")

        response = requests.post(
            f"{self.api_base}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": disable_preview,
            },
            timeout=30,
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data

    def post_to_channel(self, text: str) -> dict:
        if not self.channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID is not set")
        return self._send(self.channel_id, text)

    def notify_owner(self, text: str) -> dict:
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        return self._send(self.notify_chat_id, text)
