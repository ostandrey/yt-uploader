"""Unified desk card status + access layer (shorts + editorial).

Minimal contract — one status enum and one get_desk_items(scope) so Today/History
do not diverge per storage backend (SQLite marks vs editorial JSON/SQLite).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

DESK_QUEUED = "desk_queued"
DESK_POSTED = "desk_posted"
DESK_SKIPPED = "desk_skipped"
STATUSES = frozenset({DESK_QUEUED, DESK_POSTED, DESK_SKIPPED})

# Open (queued) cards stay on Today past midnight so the desk does not look empty
# while History fills with unfinished work.
OPEN_TODAY_HOURS = 36.0


def normalize_status(item: dict[str, Any]) -> str:
    raw = str(item.get("status") or "").strip()
    if raw in STATUSES:
        return raw
    if item.get("done"):
        return DESK_POSTED
    if item.get("skipped") or item.get("skip_reason"):
        return DESK_SKIPPED
    return DESK_QUEUED


def apply_status(
    item: dict[str, Any],
    status: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    status = status if status in STATUSES else DESK_QUEUED
    row = dict(item)
    row["status"] = status
    row["done"] = status == DESK_POSTED
    if status == DESK_SKIPPED:
        row["skip_reason"] = (reason or row.get("skip_reason") or "").strip()
    else:
        row["skip_reason"] = ""
    return row


def _parse_iso(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(created_at: str, now: Optional[datetime] = None) -> Optional[float]:
    dt = _parse_iso(created_at)
    if not dt:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600.0)


def created_sort_key(item: dict[str, Any]) -> str:
    return str(item.get("created_at") or item.get("updated_at") or "")


def in_today_scope(
    *,
    status: str,
    day: str,
    today: str,
    age: Optional[float],
) -> bool:
    """Today = open work under OPEN_TODAY_HOURS, or calendar-today posted/skipped."""
    if status == DESK_QUEUED:
        if age is None:
            return day == today
        return age < OPEN_TODAY_HOURS
    return day == today


def short_card_status(pack: dict[str, Any]) -> str:
    marks = pack.get("marks") if isinstance(pack.get("marks"), dict) else {}
    # Manual desk flow marks TT + IG; Threads mark UI is not on Short panel.
    platforms = ("tiktok", "instagram")
    if all(marks.get(p) for p in platforms):
        return DESK_POSTED
    if pack.get("skipped") or pack.get("skip_reason"):
        return DESK_SKIPPED
    return DESK_QUEUED


def get_desk_items(
    *,
    scope: str = "today",
    item_type: Optional[str] = None,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Single access point for desk cards.

    scope: today | history | all
    item_type: editorial | short | None (both)
    """
    from src.desk import catalog, db

    now = now or datetime.now(timezone.utc)
    today = catalog._today_key()
    out: list[dict[str, Any]] = []

    if item_type in (None, "editorial"):
        for raw in catalog._raw_editorial_items():
            status = normalize_status(raw)
            created_at = str(raw.get("created_at") or "")
            age = age_hours(created_at, now)
            day = catalog._day_key(created_at)
            if scope == "today" and not in_today_scope(
                status=status, day=day, today=today, age=age
            ):
                continue
            if scope == "history" and in_today_scope(
                status=status, day=day, today=today, age=age
            ):
                continue
            row = catalog._enrich_editorial(apply_status(raw, status), now)
            row["item_type"] = "editorial"
            row["status"] = status
            row["age_hours"] = age
            out.append(row)

    if item_type in (None, "short"):
        for pack in db.list_shorts(80):
            created_at = str(pack.get("created_at") or pack.get("updated_at") or "")
            updated_at = str(pack.get("updated_at") or created_at)
            status = short_card_status(pack)
            age = age_hours(created_at, now)
            day = catalog._day_key(updated_at or created_at)
            if scope == "today" and not in_today_scope(
                status=status, day=day, today=today, age=age
            ):
                continue
            if scope == "history" and in_today_scope(
                status=status, day=day, today=today, age=age
            ):
                continue
            row = dict(pack)
            row.update(
                {
                    "item_type": "short",
                    "status": status,
                    "done": status == DESK_POSTED,
                    "created_at": created_at,
                    "day": day,
                    "age_hours": age,
                    "when": catalog._short_ts(updated_at),
                }
            )
            out.append(row)

    out.sort(
        key=lambda row: (
            row.get("status") != DESK_QUEUED,
            not bool(row.get("is_new")),
            created_sort_key(row),
        )
    )
    return out
