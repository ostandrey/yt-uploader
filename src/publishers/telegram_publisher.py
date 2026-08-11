"""
Telegram publisher for Coin Wire channel and personal notifications.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
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

    def send_owner_video(
        self,
        video_path: Path,
        caption: str,
        *,
        buttons: Optional[ButtonsArg] = None,
        max_bytes: int = 49_000_000,
    ) -> dict:
        """Send MP4 to owner chat so they can re-upload from a phone."""
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        if not self.bot_token:
            raise ValueError("TELEGRAM bot token is missing")
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        size = video_path.stat().st_size
        if size > max_bytes:
            raise ValueError(
                f"Video too large for Telegram bot API ({size} bytes, max {max_bytes})"
            )
        payload = {
            "chat_id": self.notify_chat_id,
            "caption": caption[:1024],
            "supports_streaming": "true",
        }
        keyboard = normalize_keyboard(buttons)
        if keyboard:
            payload["reply_markup"] = json.dumps(
                {"inline_keyboard": keyboard}, ensure_ascii=False
            )
        with video_path.open("rb") as handle:
            response = requests.post(
                f"{self.api_base}/sendVideo",
                data=payload,
                files={"video": (video_path.name, handle, "video/mp4")},
                timeout=180,
            )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram sendVideo error: {data}")
        return data

    def send_owner_album(self, image_paths: list[Path], caption: str = "") -> dict:
        """sendMediaGroup — carousel JPEGs as one album."""
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        if not self.bot_token:
            raise ValueError("TELEGRAM bot token is missing")
        paths = [Path(p) for p in image_paths if Path(p).is_file()][:10]
        if len(paths) < 2:
            if not paths:
                raise FileNotFoundError("no carousel images")
            return self.send_owner_photo(paths[0], caption)
        media = []
        files = {}
        handles = []
        try:
            for index, path in enumerate(paths):
                key = f"photo{index}"
                handle = path.open("rb")
                handles.append(handle)
                files[key] = (path.name, handle, "image/jpeg")
                item = {"type": "photo", "media": f"attach://{key}"}
                if index == 0 and caption.strip():
                    item["caption"] = caption.strip()[:1024]
                media.append(item)
            response = requests.post(
                f"{self.api_base}/sendMediaGroup",
                data={
                    "chat_id": self.notify_chat_id,
                    "media": json.dumps(media),
                },
                files=files,
                timeout=120,
            )
        finally:
            for handle in handles:
                handle.close()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram sendMediaGroup error: {data}")
        return data

    def send_owner_photo(self, image_path: Path, caption: str = "") -> dict:
        if not self.notify_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")
        if not self.bot_token:
            raise ValueError("TELEGRAM bot token is missing")
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        payload = {"chat_id": self.notify_chat_id}
        if caption.strip():
            payload["caption"] = caption.strip()[:1024]
        with image_path.open("rb") as handle:
            response = requests.post(
                f"{self.api_base}/sendPhoto",
                data=payload,
                files={"photo": (image_path.name, handle, "image/jpeg")},
                timeout=60,
            )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram sendPhoto error: {data}")
        return data

    def send_owner_copy_packs(self, packs: list[tuple[str, str]]) -> None:
        """Two messages per platform: hint, then copyable body only."""
        for hint, body in packs:
            body = (body or "").strip()
            if not body:
                continue
            self.notify_owner(hint)
            self.notify_owner(body)
