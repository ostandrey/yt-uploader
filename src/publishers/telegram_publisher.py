"""
Telegram publisher for Coin Wire channel and personal notifications.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Sequence, Union

import requests
from dotenv import load_dotenv

# One row of buttons, or a full keyboard (list of rows).
ButtonRow = List[dict]
Keyboard = List[ButtonRow]
ButtonsArg = Union[ButtonRow, Keyboard]


def normalize_keyboard(buttons: Optional[ButtonsArg]) -> Optional[Keyboard]:
    """Accept a single row or a list of rows."""
    if not buttons:
        return None
    if isinstance(buttons[0], list):
        return buttons  # type: ignore[return-value]
    return [buttons]  # type: ignore[list-item]


def control_keyboard(video_id: Optional[str] = None) -> Keyboard:
    """Owner control buttons for bot notifications."""
    rows: Keyboard = []
    if video_id:
        rows.append([
            {"text": "Publish now", "callback_data": f"cw:pub:{video_id}"},
            {"text": "Hold", "callback_data": f"cw:hold:{video_id}"},
        ])
    rows.append([
        {"text": "Status", "callback_data": "cw:status"},
        {"text": "Pause AP", "callback_data": "cw:ap:off"},
        {"text": "Resume AP", "callback_data": "cw:ap:on"},
    ])
    return rows


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
        buttons: Optional[ButtonsArg] = None,
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
        keyboard = normalize_keyboard(buttons)
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}

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

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        if not self.bot_token or not callback_query_id:
            return
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:200]
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            requests.post(
                f"{self.api_base}/answerCallbackQuery",
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15,
            )
        except requests.RequestException:
            pass

    def post_to_channel(self, text: str) -> dict:
        if not self.channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID is not set")
        return self._send(self.channel_id, text)

    def post_to_channel_html(
        self,
        text: str,
        *,
        buttons: Optional[ButtonsArg] = None,
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

    def notify_owner(
        self,
        text: str,
        *,
        buttons: Optional[ButtonsArg] = None,
    ) -> dict:
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        return self._send(self.notify_chat_id, text, buttons=buttons)
