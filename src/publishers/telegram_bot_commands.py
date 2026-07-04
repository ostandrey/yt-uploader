"""
Telegram bot commands for owner — control auto-publish without Railway UI.
Supports slash commands and inline button callbacks.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

from src.publishers.pending_publish import (
    auto_publish_delay_minutes,
    hold_scheduled,
    load_pending,
    mark_published,
)
from src.publishers.runtime_settings import (
    auto_publish_resolved,
    env_auto_publish_lock,
    get_bot_update_offset,
    set_bot_update_offset,
    set_runtime_auto_publish,
)
from src.publishers.telegram_publisher import TelegramPublisher, control_keyboard
from src.publishers.youtube_publisher import YouTubePublisher

log = logging.getLogger(__name__)

HELP_TEXT = """Coin Wire bot commands

/status — auto-publish state + queue
/autopublish on — enable auto-publish
/autopublish off — pause auto-publish
/pause — same as autopublish off
/resume — same as autopublish on
/hold VIDEO_ID — keep one Short unlisted
/publish VIDEO_ID — publish now (skip wait)
/help — this message

Or use the buttons under notifications."""


def _owner_chat_id() -> str:
    load_dotenv()
    return (os.getenv("TELEGRAM_CHAT_ID") or "").strip()


def _bot_token() -> str:
    load_dotenv()
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _publisher() -> TelegramPublisher:
    return TelegramPublisher()


def _reply(chat_id: str, text: str, *, with_controls: bool = True) -> None:
    buttons = control_keyboard() if with_controls else None
    _publisher()._send(chat_id, text, buttons=buttons)


def _status_text() -> str:
    enabled, source = auto_publish_resolved()
    delay = auto_publish_delay_minutes()
    pending = load_pending()
    scheduled = [e for e in pending if e.get("status") == "scheduled"]

    source_labels = {
        "env_off": "LOCKED OFF (YOUTUBE_AUTO_PUBLISH=0 on server)",
        "env_on": "forced ON (YOUTUBE_AUTO_PUBLISH=1 on server)",
        "bot": "set via Telegram bot",
        "runtime": "runtime settings file",
        "yaml_default": "config default",
    }
    lines = [
        "Coin Wire status",
        "",
        f"Auto-publish: {'ON' if enabled else 'OFF'}",
        f"Source: {source_labels.get(source, source)}",
        f"Delay: {delay} min after upload",
        f"Scheduled Shorts: {len(scheduled)}",
    ]
    for entry in scheduled[:5]:
        lines.append(f"  - {entry['video_id']}: {entry.get('title', '')[:50]}")
        if entry.get("publish_at"):
            lines.append(f"    at {entry['publish_at'][:16].replace('T', ' ')} UTC")
    if len(scheduled) > 5:
        lines.append(f"  ... +{len(scheduled) - 5} more")
    return "\n".join(lines)


def _set_auto_publish(chat_id: str, enabled: bool) -> None:
    lock = env_auto_publish_lock()
    if lock is not None:
        if lock is False and enabled:
            _reply(
                chat_id,
                "Auto-publish is LOCKED OFF via YOUTUBE_AUTO_PUBLISH=0 on Railway.\n"
                "Remove or change that variable to enable from bot.",
            )
            return
        if lock is True and not enabled:
            _reply(
                chat_id,
                "Auto-publish is forced ON via YOUTUBE_AUTO_PUBLISH=1 on Railway.\n"
                "Set YOUTUBE_AUTO_PUBLISH=0 to allow bot control.",
            )
            return

    set_runtime_auto_publish(enabled)
    state = "ON" if enabled else "OFF"
    _reply(chat_id, f"Auto-publish is now {state} (via bot).")


def _publish_now(chat_id: str, video_id: str) -> None:
    publisher = YouTubePublisher()
    publisher.set_privacy(video_id, "public")
    mark_published(video_id)
    hold_scheduled(video_id)
    url = YouTubePublisher.short_url(video_id)
    _reply(chat_id, f"Published now:\n{url}")


def _hold_video(chat_id: str, video_id: str) -> None:
    if hold_scheduled(video_id):
        _reply(chat_id, f"Held {video_id} - will stay unlisted.")
    else:
        _reply(chat_id, f"No scheduled auto-publish found for {video_id}.")


def handle_command(text: str, chat_id: str) -> bool:
    """Process one slash command. Returns True if handled."""
    if str(chat_id) != _owner_chat_id():
        log.warning("Ignored command from unauthorized chat %s", chat_id)
        return False

    cmd = (text or "").strip()
    if not cmd.startswith("/"):
        return False

    parts = cmd.split()
    name = parts[0].lower().split("@")[0]

    if name in ("/start", "/help"):
        _reply(chat_id, HELP_TEXT)
        return True

    if name == "/status":
        _reply(chat_id, _status_text())
        return True

    if name in ("/pause",):
        _set_auto_publish(chat_id, False)
        return True

    if name in ("/resume",):
        _set_auto_publish(chat_id, True)
        return True

    if name == "/autopublish":
        if len(parts) < 2:
            _reply(chat_id, "Usage: /autopublish on | off")
            return True
        arg = parts[1].lower()
        if arg in ("on", "1", "true", "yes"):
            _set_auto_publish(chat_id, True)
        elif arg in ("off", "0", "false", "no"):
            _set_auto_publish(chat_id, False)
        else:
            _reply(chat_id, "Usage: /autopublish on | off")
        return True

    if name == "/hold" and len(parts) >= 2:
        _hold_video(chat_id, parts[1].strip())
        return True

    if name == "/publish" and len(parts) >= 2:
        try:
            _publish_now(chat_id, parts[1].strip())
        except Exception as exc:
            _reply(chat_id, f"Publish failed: {exc}")
        return True

    return False


def handle_callback(data: str, chat_id: str, callback_id: str) -> bool:
    """Process an inline button press. Returns True if handled."""
    pub = _publisher()
    if str(chat_id) != _owner_chat_id():
        pub.answer_callback(callback_id, "Unauthorized")
        log.warning("Ignored callback from unauthorized chat %s", chat_id)
        return False

    payload = (data or "").strip()
    if not payload.startswith("cw:"):
        pub.answer_callback(callback_id)
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "status":
            pub.answer_callback(callback_id, "Status")
            _reply(chat_id, _status_text())
            return True

        if action == "ap" and len(parts) >= 3:
            enabled = parts[2] == "on"
            pub.answer_callback(callback_id, "ON" if enabled else "OFF")
            _set_auto_publish(chat_id, enabled)
            return True

        if action == "pub" and len(parts) >= 3:
            video_id = parts[2]
            pub.answer_callback(callback_id, "Publishing...")
            try:
                _publish_now(chat_id, video_id)
            except Exception as exc:
                _reply(chat_id, f"Publish failed: {exc}")
            return True

        if action == "hold" and len(parts) >= 3:
            video_id = parts[2]
            pub.answer_callback(callback_id, "Holding...")
            _hold_video(chat_id, video_id)
            return True
    except Exception as exc:
        log.exception("Callback failed: %s", exc)
        pub.answer_callback(callback_id, "Error")
        _reply(chat_id, f"Button action failed: {exc}")
        return True

    pub.answer_callback(callback_id)
    return False


def poll_commands_once() -> int:
    """Fetch and process pending bot commands/callbacks. Returns number handled."""
    token = _bot_token()
    owner = _owner_chat_id()
    if not token or not owner:
        return 0

    offset = get_bot_update_offset()
    response = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={
            "offset": offset,
            "timeout": 0,
            "allowed_updates": '["message","callback_query"]',
        },
        timeout=15,
    )
    data = response.json()
    if not data.get("ok"):
        log.warning("getUpdates failed: %s", data)
        return 0

    handled = 0
    max_id = offset
    for update in data.get("result", []):
        update_id = int(update.get("update_id", 0))
        max_id = max(max_id, update_id + 1)

        callback = update.get("callback_query")
        if callback:
            cb_id = str(callback.get("id", ""))
            cb_data = callback.get("data") or ""
            message = callback.get("message") or {}
            chat = message.get("chat") or callback.get("from") or {}
            chat_id = str(chat.get("id", ""))
            if handle_callback(cb_data, chat_id, cb_id):
                handled += 1
            continue

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = message.get("text") or ""
        if handle_command(text, chat_id):
            handled += 1

    if max_id > offset:
        set_bot_update_offset(max_id)

    return handled
