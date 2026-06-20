"""
Telegram publisher for Coin Wire channel and personal notifications.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

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

    def _send(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        disable_preview: bool = False,
        buttons: Optional[List[dict]] = None,
    ) -> dict:
        if not self.bot_token or not chat_id:
            raise ValueError("Telegram bot token or chat id is missing")

        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [buttons]}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response = requests.post(
            f"{self.api_base}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
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

    def post_to_channel_html(
        self,
        text: str,
        *,
        buttons: Optional[List[dict]] = None,
    ) -> dict:
        if not self.channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID is not set")
        return self._send(
            self.channel_id,
            text,
            parse_mode="HTML",
            disable_preview=True,
            buttons=buttons,
        )

    def notify_owner(self, text: str) -> dict:
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        return self._send(self.notify_chat_id, text)
