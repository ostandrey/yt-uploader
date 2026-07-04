"""
Queue and auto-publish YouTube Shorts after a processing delay.

Kill switch (checked at schedule time AND publish time):
  YOUTUBE_AUTO_PUBLISH=0|false|off   — disable
  YOUTUBE_AUTO_PUBLISH=1|true|on     — force enable (overrides yaml false)
  unset — use config/coin_wire.yaml
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.publishers.runtime_settings import auto_publish_resolved

ROOT = Path(__file__).resolve().parents[2]
PENDING_FILE = ROOT / "data" / "storage" / "coin_wire" / "pending_uploads.json"


def _load_config() -> dict:
    config_path = ROOT / "config" / "coin_wire.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def auto_publish_enabled(config: Optional[dict] = None) -> bool:
    enabled, _source = auto_publish_resolved(config)
    return enabled


def auto_publish_delay_minutes(config: Optional[dict] = None) -> int:
    cfg = config or _load_config()
    return int(
        cfg.get("publishing", {}).get("youtube", {}).get("auto_publish_delay_minutes", 30)
    )


def load_pending() -> List[Dict[str, Any]]:
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_pending(entries: List[Dict[str, Any]]) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = entries[-100:]
    PENDING_FILE.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")


def add_pending_upload(
    video_id: str,
    title: str,
    *,
    schedule_auto_publish: bool,
    delay_minutes: int = 30,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    entry: Dict[str, Any] = {
        "video_id": video_id,
        "title": title,
        "privacy": "unlisted",
        "status": "unlisted",
        "uploaded_at": now.isoformat(),
        "publish_at": None,
    }
    if schedule_auto_publish:
        entry["status"] = "scheduled"
        entry["publish_at"] = (now + timedelta(minutes=delay_minutes)).isoformat()

    pending = load_pending()
    pending = [e for e in pending if e.get("video_id") != video_id]
    pending.append(entry)
    save_pending(pending)
    return entry


def mark_published(video_id: str) -> None:
    pending = load_pending()
    for entry in pending:
        if entry.get("video_id") == video_id:
            entry["status"] = "published"
            entry["privacy"] = "public"
            entry["published_at"] = datetime.now(timezone.utc).isoformat()
            entry["publish_at"] = None
    save_pending(pending)


def hold_scheduled(video_id: str) -> bool:
    """Cancel auto-publish for one video (keep unlisted)."""
    pending = load_pending()
    found = False
    for entry in pending:
        if entry.get("video_id") == video_id and entry.get("status") == "scheduled":
            entry["status"] = "held"
            entry["publish_at"] = None
            found = True
    if found:
        save_pending(pending)
    return found


def due_for_publish(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    if not auto_publish_enabled():
        return []
    now = now or datetime.now(timezone.utc)
    due: List[Dict[str, Any]] = []
    for entry in load_pending():
        if entry.get("status") != "scheduled":
            continue
        publish_at = entry.get("publish_at")
        if not publish_at:
            continue
        try:
            target = datetime.fromisoformat(publish_at)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if target <= now:
            due.append(entry)
    return due


def publish_due_shorts(*, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Publish all scheduled Shorts whose delay has elapsed."""
    from src.publishers.telegram_publisher import TelegramPublisher
    from src.publishers.youtube_publisher import YouTubePublisher

    results: List[Dict[str, Any]] = []
    due = due_for_publish()
    if not due:
        return results

    publisher = YouTubePublisher()
    for entry in due:
        video_id = entry["video_id"]
        title = entry.get("title", "")
        if dry_run:
            results.append({"video_id": video_id, "title": title, "dry_run": True})
            continue

        publisher.set_privacy(video_id, "public")
        mark_published(video_id)
        url = YouTubePublisher.short_url(video_id)
        results.append({"video_id": video_id, "title": title, "url": url})

        try:
            from src.publishers.telegram_publisher import control_keyboard

            TelegramPublisher().notify_owner(
                "Coin Wire Short is now PUBLIC (auto-publish):\n"
                f"{url}\n\n"
                f"Title: {title}",
                buttons=control_keyboard(),
            )
        except Exception:
            pass

    return results
