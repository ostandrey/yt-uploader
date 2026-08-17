"""Rolling log of posted stories — feeds weekly digest / recap / polls."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.paths import coin_wire_storage

LOG_FILE = coin_wire_storage() / "editorial_log.json"
MAX_ITEMS = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_log(path: Optional[Path] = None) -> list[dict[str, Any]]:
    path = path or LOG_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def append_event(
    *,
    kind: str,
    title: str,
    summary: str = "",
    tier: str = "",
    article_hash: str = "",
    extra: Optional[dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    path = path or LOG_FILE
    item = {
        "ts": _now_iso(),
        "kind": kind,
        "title": (title or "").strip(),
        "summary": (summary or "").strip()[:400],
        "tier": tier,
        "hash": article_hash,
    }
    if extra:
        item.update(extra)
    items = load_log(path)
    items.append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"items": items[-MAX_ITEMS:]}, indent=2),
        encoding="utf-8",
    )
    return item


def events_since(
    days: int = 7,
    *,
    kinds: Optional[set[str]] = None,
    path: Optional[Path] = None,
    tz_name: str = "America/New_York",
) -> list[dict[str, Any]]:
    path = path or LOG_FILE
    cutoff = datetime.now(ZoneInfo(tz_name)) - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for item in load_log(path):
        if kinds and item.get("kind") not in kinds:
            continue
        raw = str(item.get("ts") or "")
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff.astimezone(timezone.utc):
            out.append(item)
    return out


def format_events_list(items: list[dict[str, Any]], limit: int = 5) -> str:
    lines = []
    for item in items[-limit:]:
        title = (item.get("title") or "").strip()
        if title:
            lines.append(f"- {title}")
    return "\n".join(lines)
