"""Latest Short pack: SQLite + JSON fallback + video folder scan."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.desk import db
from src.paths import coin_wire_storage

_MONTHS_UK = (
    "",
    "січ",
    "лют",
    "бер",
    "кві",
    "тра",
    "чер",
    "лип",
    "серп",
    "вер",
    "жов",
    "лис",
    "груд",
)

ROOT = Path(__file__).resolve().parents[2]
STORAGE = coin_wire_storage()
VIDEOS_DIR = STORAGE / "videos"
LATEST_FILE = STORAGE / "desk_latest.json"
HISTORY_FILE = STORAGE / "desk_history.json"
PENDING_FILE = STORAGE / "pending_uploads.json"
USED_FILE = STORAGE / "used_short_articles.json"

DEGRADED_UA = {
    "no_music": "немає музики",
    "sfx_tones": "SFX з тонів, не файли",
    "llm_failed": "LLM не спрацював — rules copy",
}


def parse_degraded(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def degraded_labels(raw: Any) -> list[str]:
    return [DEGRADED_UA.get(flag, flag) for flag in parse_degraded(raw)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_desk_pack(
    *,
    title: str,
    video_path: Path,
    work_dir: Path,
    ig_caption: str = "",
    threads_text: str = "",
    youtube_url: str = "",
    qa_score: Optional[int] = None,
    copy_source: str = "",
    degraded: Optional[list[str]] = None,
    tiktok_caption: str = "",
) -> dict[str, Any]:
    video_path = Path(video_path)
    flags = [str(item) for item in (degraded or []) if str(item).strip()]
    pack = {
        "title": title.strip(),
        "ig_caption": (ig_caption or "").strip(),
        "tiktok_caption": (tiktok_caption or "").strip(),
        "threads_text": (threads_text or "").strip(),
        "youtube_url": (youtube_url or "").strip(),
        "video_path": str(video_path),
        "work_dir": str(work_dir),
        "updated_at": _now(),
        "qa_score": qa_score,
        "bytes": video_path.stat().st_size if video_path.is_file() else 0,
        "copy_source": (copy_source or "").strip(),
        "degraded": ",".join(flags),
    }
    if not pack["tiktok_caption"] and pack["ig_caption"]:
        from src.publishers.captions import build_tiktok_caption

        pack["tiktok_caption"] = build_tiktok_caption(
            pack["ig_caption"], title=pack["title"]
        )
    STORAGE.mkdir(parents=True, exist_ok=True)
    LATEST_FILE.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    sync_carousel(work_dir)
    saved = db.upsert_short(pack)
    pack.update(saved)
    try:
        from src.desk.push import notify_desk_push

        pushed = notify_desk_push(
            "Short ready",
            "TikTok · IG Reel · carousel on desk",
            url="/?tab=tiktok",
            tag="cw-desk-short",
        )
        print(
            f"Desk web push (short): reason={pushed.get('reason')} "
            f"sent={pushed.get('sent')} subs={pushed.get('subs')}"
        )
    except Exception as exc:
        print(f"Desk push notify failed: {exc}")
    return pack


def load_latest() -> Optional[dict[str, Any]]:
    row = db.latest_short()
    if row:
        video = Path(str(row.get("video_path") or ""))
        if video.is_file():
            row["bytes"] = video.stat().st_size
            return row
    return _from_json_or_folder()


def _from_json_or_folder() -> Optional[dict[str, Any]]:
    pack: Optional[dict[str, Any]] = None
    if LATEST_FILE.exists():
        try:
            loaded = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                pack = loaded
        except (OSError, json.JSONDecodeError):
            pack = None
    if pack:
        video = Path(str(pack.get("video_path") or ""))
        if video.is_file():
            pack["bytes"] = video.stat().st_size
            pack.setdefault("marks", {name: False for name in db.PLATFORMS})
            return pack
    return _latest_from_videos_dir()


def _latest_from_videos_dir() -> Optional[dict[str, Any]]:
    if not VIDEOS_DIR.is_dir():
        return None
    videos = sorted(VIDEOS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        return None
    video = videos[0]
    return {
        "title": video.stem.replace("_", " "),
        "ig_caption": "",
        "threads_text": "",
        "youtube_url": "",
        "video_path": str(video),
        "work_dir": "",
        "updated_at": datetime.fromtimestamp(video.stat().st_mtime, timezone.utc).isoformat(),
        "qa_score": None,
        "bytes": video.stat().st_size,
        "fallback": True,
        "marks": {name: False for name in db.PLATFORMS},
    }


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def resolve_video_file(pack: dict[str, Any]) -> Optional[Path]:
    path = Path(str(pack.get("video_path") or ""))
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    if _under(resolved, VIDEOS_DIR) or _under(resolved, STORAGE):
        return resolved
    return None


def carousel_dir() -> Path:
    return STORAGE / "ig_carousel"


def sync_carousel(work_dir: Path) -> list[Path]:
    """Copy rendered slides onto the volume so desk survives render-folder cleanup."""
    src = Path(work_dir) / "ig_carousel"
    dest = carousel_dir()
    dest.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != src.resolve():
        for old in dest.glob("*"):
            if old.is_file():
                old.unlink()
        if src.is_dir():
            for item in src.iterdir():
                if item.suffix.lower() in {".jpg", ".jpeg", ".txt"} and item.is_file():
                    shutil.copy2(item, dest / item.name)
    return list_carousel_slides()


def list_carousel_slides() -> list[Path]:
    folder = carousel_dir()
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.jpg") if p.is_file() and _under(p, folder))


def used_short_hashes() -> set[str]:
    path = STORAGE / "used_short_articles.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("hashes") or [])
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def _editorial_path() -> Path:
    return STORAGE / "desk_editorial.json"


def _desk_tz() -> ZoneInfo:
    name = (os.getenv("DESK_TZ") or os.getenv("TZ") or "America/New_York").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _today_key() -> str:
    return datetime.now(_desk_tz()).strftime("%Y-%m-%d")


def _day_key(iso: str) -> str:
    if not iso:
        return _today_key()
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return _today_key()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(_desk_tz()).strftime("%Y-%m-%d")


def _day_label(day: str) -> str:
    try:
        ts = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return day
    month = _MONTHS_UK[ts.month] if 1 <= ts.month <= 12 else ""
    return f"{ts.day} {month}".strip()


def _json_editorial_items() -> list[dict[str, Any]]:
    path = _editorial_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        created_at = str(item.get("created_at") or item.get("ts") or "").strip()
        item_id = str(item.get("id") or "").strip() or f"e{index}-{hash(text) & 0xFFFF:x}"
        out.append(
            {
                "id": item_id,
                "kind": str(item.get("kind") or "note"),
                "label": str(item.get("label") or item.get("kind") or "Copy"),
                "text": text,
                "created_at": created_at,
                "done": bool(item.get("done")),
            }
        )
    return out


def _raw_editorial_items() -> list[dict[str, Any]]:
    json_items = _json_editorial_items()
    try:
        db.migrate_editorial_from_json(json_items)
        rows = db.list_editorial()
    except Exception:
        rows = []
    return rows or json_items


def _enrich_editorial(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    created_at = str(item.get("created_at") or "")
    done = bool(item.get("done"))
    age_hours = _age_hours(created_at, now)
    is_new = (not done) and age_hours is not None and age_hours < 8
    kind = str(item.get("kind") or "note")
    if kind in {"opinion", "question", "recap"}:
        tab = "threads"
    elif kind in {"context", "poll", "digest"}:
        tab = "telegram"
    else:
        tab = "threads"
    text = str(item.get("text") or "")
    first = (text.splitlines()[0] if text else "").strip()
    snip = first if len(first) <= 72 else first[:71].rstrip() + "…"
    row = dict(item)
    row.update(
        {
            "kind": kind,
            "tab": tab,
            "day": _day_key(created_at),
            "is_new": is_new,
            "badge": "НОВЕ" if is_new else ("ГОТОВО" if done else "РАНІШЕ"),
            "badge_kind": "new" if is_new else ("done" if done else "old"),
            "when": _short_ts(created_at) if created_at else "",
            "age": _age_label(age_hours),
            "snip": snip,
        }
    )
    return row


def split_question_post(text: str) -> Optional[dict[str, str]]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 3:
        return None
    return {"question": lines[0], "a": lines[1], "b": lines[2]}


def next_check_label(interval_minutes: int = 30) -> str:
    now = datetime.now(_desk_tz())
    total = now.hour * 60 + now.minute
    step = max(int(interval_minutes), 1)
    wait = step - (total % step)
    if wait == step:
        wait = step
    return f"Наступна перевірка: ~{wait} хв"


def load_editorial_items(*, scope: str = "today") -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    today = _today_key()
    out: list[dict[str, Any]] = []
    for item in _raw_editorial_items():
        row = _enrich_editorial(item, now)
        day = str(row.get("day") or today)
        if scope == "today" and day != today:
            continue
        if scope == "history" and day == today:
            continue
        out.append(row)
    out.sort(
        key=lambda row: (
            bool(row.get("done")),
            not bool(row.get("is_new")),
            str(row.get("created_at") or ""),
        )
    )
    return out


def editorial_history_count() -> int:
    today = _today_key()
    return sum(1 for item in _raw_editorial_items() if _day_key(str(item.get("created_at") or "")) != today)


def history_page() -> dict[str, Any]:
    today = _today_key()
    groups: dict[str, dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    for item in load_editorial_items(scope="history"):
        day = str(item.get("day") or "")
        if not day:
            continue
        bucket = groups.setdefault(
            day,
            {"day": day, "label": _day_label(day), "editorial": [], "shorts": []},
        )
        bucket["editorial"].append(item)
    for short in db.list_shorts(80):
        day = _day_key(str(short.get("updated_at") or short.get("created_at") or ""))
        if not day or day == today:
            continue
        bucket = groups.setdefault(
            day,
            {"day": day, "label": _day_label(day), "editorial": [], "shorts": []},
        )
        row = dict(short)
        row["when"] = _short_ts(str(short.get("updated_at") or ""))
        bucket["shorts"].append(row)
    ordered = sorted(groups.values(), key=lambda row: str(row.get("day") or ""), reverse=True)
    from src.paths import storage_status

    storage = storage_status()
    return {
        "groups": ordered,
        "count": sum(len(g["editorial"]) + len(g["shorts"]) for g in ordered),
        "storage_warn": bool(storage.get("warn_no_volume")),
        "storage_path": storage.get("path") or "",
    }


def desk_stamp() -> dict[str, Any]:
    latest = load_latest() or {}
    editorial = load_editorial_items(scope="today")
    return {
        "editorial": len(editorial),
        "open": sum(1 for item in editorial if not item.get("done")),
        "latest_at": str(latest.get("updated_at") or ""),
        "newest": str((editorial[0] or {}).get("created_at") or "") if editorial else "",
    }


def write_editorial_items(items: list[dict[str, Any]]) -> None:
    STORAGE.mkdir(parents=True, exist_ok=True)
    now = _now()
    payload_items = [
        {
            "id": str(item.get("id") or f"e-{hash(str(item.get('text') or '')) & 0xFFFFF:x}"),
            "kind": str(item.get("kind") or "note"),
            "label": str(item.get("label") or item.get("kind") or "Copy"),
            "text": str(item.get("text") or "").strip(),
            "created_at": str(item.get("created_at") or now),
            "done": bool(item.get("done")),
        }
        for item in items
        if str(item.get("text") or "").strip()
    ]
    payload = {"updated_at": now, "items": payload_items}
    _editorial_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    db.replace_editorial(payload_items)


def set_editorial_done(item_id: str, done: bool = True) -> Optional[dict[str, Any]]:
    items = _raw_editorial_items()
    found = None
    for item in items:
        if item.get("id") == item_id:
            item["done"] = bool(done)
            found = item
            break
    if not found:
        return None
    write_editorial_items(items)
    enriched = next(
        (row for row in load_editorial_items(scope="all") if row.get("id") == item_id),
        None,
    )
    return enriched or found


def _age_hours(iso: str, now: Optional[datetime] = None) -> Optional[float]:
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - ts.astimezone(timezone.utc)).total_seconds() / 3600)


def _age_label(hours: Optional[float]) -> str:
    if hours is None:
        return ""
    if hours < 1:
        return "щойно"
    if hours < 24:
        return f"{int(hours)} год тому"
    days = int(hours // 24)
    return f"{days} дн тому"


def carousel_caption_text() -> str:
    folder = carousel_dir()
    path = folder / "caption.txt"
    if not path.is_file() or not _under(path, folder):
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def resolve_carousel_slide(name: str) -> Optional[Path]:
    safe = Path(name).name
    if safe != name or not safe.endswith(".jpg"):
        return None
    folder = carousel_dir()
    path = (folder / safe).resolve()
    if path.is_file() and _under(path, folder):
        return path
    return None


def resolve_thumb(pack: dict[str, Any]) -> Optional[Path]:
    work = Path(str(pack.get("work_dir") or ""))
    thumb = work / "thumbnail.jpg"
    try:
        resolved = thumb.resolve()
    except OSError:
        return None
    if resolved.is_file() and _under(resolved, STORAGE):
        return resolved
    return None


def desk_tabs(pack: dict | None, editorial: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tab strip: unpublished counts (open work), not only НОВЕ."""
    threads_kinds = {"opinion", "question", "recap"}
    telegram_kinds = {"context", "poll", "digest"}
    threads_new = sum(
        1
        for item in editorial
        if (not item.get("done")) and item.get("kind") in threads_kinds
    )
    telegram_new = sum(
        1
        for item in editorial
        if (not item.get("done")) and item.get("kind") in telegram_kinds
    )
    short_new = 0
    tiktok_new = 0
    ig_new = 0
    if pack:
        marks = pack.get("marks") or {}
        if not marks.get("tiktok"):
            tiktok_new = 1
            short_new += 1
        if not marks.get("instagram"):
            ig_new = 1
            short_new += 1
    return [
        {"id": "threads", "label": "Threads", "badge": threads_new},
        {"id": "telegram", "label": "TG", "badge": telegram_new},
        {"id": "tiktok", "label": "TikTok", "badge": tiktok_new},
        {"id": "instagram", "label": "IG", "badge": ig_new},
        {"id": "short", "label": "Short", "badge": short_new},
    ]


def stats_snapshot() -> dict[str, Any]:
    pending: list[Any] = []
    if PENDING_FILE.exists():
        try:
            loaded = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                pending = loaded
        except (OSError, json.JSONDecodeError):
            pending = []
    used = 0
    if USED_FILE.exists():
        try:
            data = json.loads(USED_FILE.read_text(encoding="utf-8"))
            used = len(data.get("hashes") or [])
        except (OSError, json.JSONDecodeError):
            used = 0
    latest = load_latest()
    counts = db.mark_counts()
    history = []
    for item in db.list_shorts(12):
        row = dict(item)
        row["when"] = _short_ts(str(row.get("updated_at") or ""))
        history.append(row)

    editorial = load_editorial_items(scope="all")
    editorial_new = sum(1 for item in editorial if item.get("is_new"))
    editorial_open = sum(1 for item in editorial if not item.get("done"))
    editorial_done = sum(1 for item in editorial if item.get("done"))

    tg_today = 0
    tg_state = STORAGE / "telegram_daily_state.json"
    if tg_state.exists():
        try:
            data = json.loads(tg_state.read_text(encoding="utf-8"))
            tg_today = int(data.get("post_count") or 0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            tg_today = 0

    from src.paths import storage_status

    storage = storage_status()
    empty = (
        counts.get("shorts", 0) == 0
        and used == 0
        and not editorial
        and not pending
    )

    return {
        "shorts_on_desk": counts.get("shorts", 0),
        "posted_tiktok": counts.get("tiktok", 0),
        "posted_instagram": counts.get("instagram", 0),
        "posted_threads": counts.get("threads", 0),
        "articles_used": used,
        "pending_youtube": len(pending),
        "latest_title": (latest or {}).get("title") or "",
        "latest_at": _short_ts(str((latest or {}).get("updated_at") or "")),
        "latest_qa": (latest or {}).get("qa_score"),
        "history": history,
        "pending": pending[-8:],
        "editorial_new": editorial_new,
        "editorial_open": editorial_open,
        "editorial_done": editorial_done,
        "telegram_today": tg_today,
        "storage_path": storage.get("path") or "",
        "storage_warn": bool(storage.get("warn_no_volume") or empty and storage.get("railway")),
        "push_subs": int(storage.get("push_subs") or 0),
        "overdue_today": _overdue_today(editorial, latest),
        "platforms_today": [
            {
                "id": "telegram",
                "label": "Telegram канал",
                "done": tg_today,
                "target": 8,
            },
            {
                "id": "editorial",
                "label": "Desk тексти (нові)",
                "done": editorial_new,
                "target": max(editorial_open, 1),
            },
            {
                "id": "tiktok",
                "label": "TikTok ✓",
                "done": counts.get("tiktok", 0),
                "target": max(counts.get("shorts", 0), 1),
            },
            {
                "id": "instagram",
                "label": "IG ✓",
                "done": counts.get("instagram", 0),
                "target": max(counts.get("shorts", 0), 1),
            },
        ],
    }


def _overdue_today(editorial: list[dict[str, Any]], latest: Optional[dict[str, Any]]) -> str:
    today = _today_key()
    bits: list[str] = []
    threads_n = sum(
        1
        for item in editorial
        if not item.get("done") and item.get("tab") == "threads" and item.get("day") == today
    )
    tg_n = sum(
        1
        for item in editorial
        if not item.get("done") and item.get("tab") == "telegram" and item.get("day") == today
    )
    if threads_n:
        bits.append(f"Threads ×{threads_n}")
    if tg_n:
        bits.append(f"TG ×{tg_n}")
    marks = (latest or {}).get("marks") or {}
    if latest and not marks.get("tiktok"):
        bits.append("TikTok")
    if latest and not marks.get("instagram"):
        bits.append("IG")
    if not bits:
        return ""
    return "Незапощено сьогодні: " + ", ".join(bits)


def _short_ts(iso: str) -> str:
    return (iso or "")[:16].replace("T", " ")
