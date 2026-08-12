"""Rolling log of posted stories — feeds weekly digest / recap / polls."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

LOG_FILE = Path("data/storage/coin_wire/editorial_log.json")
MAX_ITEMS = 80


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_log(path: Path = LOG_FILE) -> list[dict[str, Any]]:
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
    path: Path = LOG_FILE,
) -> dict[str, Any]:
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
    path: Path = LOG_FILE,
    tz_name: str = "America/New_York",
) -> list[dict[str, Any]]:
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
