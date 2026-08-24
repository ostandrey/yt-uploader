"""Latest Short pack: SQLite + JSON fallback + video folder scan."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional
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
EDITORIAL_LOCK_FILE = STORAGE / "editorial.lock"

DEGRADED_UA = {
    "no_music": "немає музики",
    "music_synth": "музика — synth pad (не Pixabay)",
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


def _stable_editorial_id(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"e-{digest}"


@contextmanager
def editorial_lock(timeout_sec: float = 8.0, *, required: bool = False) -> Iterator[None]:
    """Cross-process lock for editorial read-modify-write (desk + worker jobs)."""
    EDITORIAL_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(EDITORIAL_LOCK_FILE, "a+", encoding="utf-8")
    deadline = time.monotonic() + timeout_sec
    locked = False
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    if required:
                        handle.close()
                        raise TimeoutError(
                            f"editorial.lock busy >{timeout_sec}s"
                        ) from None
                    break
                time.sleep(0.05)
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            handle.close()
        except Exception:
            pass


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
    sync_story(work_dir)
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
    return sorted(
        p
        for p in folder.glob("*.jpg")
        if p.is_file() and _under(p, folder) and re.fullmatch(r"0[1-4]\.jpg", p.name)
    )


def story_dir() -> Path:
    return STORAGE / "ig_story"


def sync_story(work_dir: Path) -> Optional[Path]:
    src = Path(work_dir) / "ig_story" / "story.jpg"
    dest_dir = story_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "story.jpg"
    if src.is_file() and dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
        return dest
    if not src.is_file() and dest.is_file():
        dest.unlink(missing_ok=True)
        return None
    if dest.is_file() and _under(dest, dest_dir):
        return dest
    return None


def story_path() -> Optional[Path]:
    path = story_dir() / "story.jpg"
    if path.is_file() and _under(path, story_dir()):
        return path
    return None


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
    from src.desk.items import apply_status, normalize_status

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
        row = {
            "id": item_id,
            "kind": str(item.get("kind") or "note"),
            "label": str(item.get("label") or item.get("kind") or "Copy"),
            "text": text,
            "created_at": created_at,
            "done": bool(item.get("done")),
            "status": str(item.get("status") or ""),
            "skip_reason": str(item.get("skip_reason") or ""),
        }
        out.append(apply_status(row, normalize_status(row)))
    return out


def _raw_editorial_items() -> list[dict[str, Any]]:
    from src.desk.items import apply_status, normalize_status

    json_items = _json_editorial_items()
    try:
        db.migrate_editorial_from_json(json_items)
        rows = db.list_editorial()
    except Exception:
        rows = []
    source = rows or json_items
    return [apply_status(row, normalize_status(row)) for row in source]


_KIND_CHIP_UA = {
    "opinion": "opinion",
    "news": "новина",
    "новина": "новина",
    "numbers": "цифри",
    "snapshot": "зріз",
    "зріз ринку": "зріз",
    "зріз": "зріз",
    "reflection": "reflection",
    "recap": "recap",
    "context": "контекст",
    "контекст": "контекст",
    "question": "питання",
    "poll": "опит",
    "digest": "дайджест",
    "note": "нотатка",
}


def kind_chip_label(kind: str) -> str:
    raw = str(kind or "note").strip()
    if not raw:
        return "нотатка"
    return _KIND_CHIP_UA.get(raw.lower(), raw)


def _enrich_editorial(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    from src.desk.items import DESK_POSTED, DESK_SKIPPED, apply_status, normalize_status

    created_at = str(item.get("created_at") or "")
    status = normalize_status(item)
    item = apply_status(item, status, reason=str(item.get("skip_reason") or ""))
    done = status == DESK_POSTED
    age_hours = _age_hours(created_at, now)
    is_new = (status != DESK_POSTED and status != DESK_SKIPPED) and age_hours is not None and age_hours < 8
    kind = str(item.get("kind") or "note")
    if kind in {"opinion", "question", "recap", "reflection", "snapshot", "news", "numbers"}:
        tab = "threads"
    elif kind in {"context", "poll", "digest"}:
        tab = "telegram"
    else:
        tab = "threads"
    text = str(item.get("text") or "")
    first = (text.splitlines()[0] if text else "").strip()
    snip = first if len(first) <= 72 else first[:71].rstrip() + "…"
    if status == DESK_SKIPPED:
        badge, badge_kind = "ПРОПУСК", "old"
    elif done:
        badge, badge_kind = "ГОТОВО", "done"
    elif is_new:
        badge, badge_kind = "НОВЕ", "new"
    else:
        badge, badge_kind = "РАНІШЕ", "old"
    row = dict(item)
    row.update(
        {
            "kind": kind,
            "kind_label": kind_chip_label(kind),
            "tab": tab,
            "day": _day_key(created_at),
            "status": status,
            "done": done,
            "is_new": is_new,
            "badge": badge,
            "badge_kind": badge_kind,
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
    from src.desk.items import get_desk_items

    return get_desk_items(scope=scope, item_type="editorial")


def editorial_history_count() -> int:
    from src.desk.items import get_desk_items

    return len(get_desk_items(scope="history", item_type="editorial"))


def history_page(*, page: int = 1, page_size: int = 7) -> dict[str, Any]:
    from math import ceil

    from src.desk.items import get_desk_items

    groups: dict[str, dict[str, Any]] = {}
    for item in get_desk_items(scope="history"):
        day = str(item.get("day") or "")
        if not day:
            continue
        bucket = groups.setdefault(
            day,
            {"day": day, "label": _day_label(day), "editorial": [], "shorts": []},
        )
        if item.get("item_type") == "short":
            bucket["shorts"].append(item)
        else:
            bucket["editorial"].append(item)
    ordered = sorted(groups.values(), key=lambda row: str(row.get("day") or ""), reverse=True)
    total_days = len(ordered)
    page_size = max(1, min(int(page_size or 7), 31))
    total_pages = max(1, ceil(total_days / page_size) if total_days else 1)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * page_size
    slice_groups = ordered[start : start + page_size]
    from src.paths import storage_status

    storage = storage_status()
    return {
        "groups": slice_groups,
        "count": sum(len(g["editorial"]) + len(g["shorts"]) for g in slice_groups),
        "total_count": sum(len(g["editorial"]) + len(g["shorts"]) for g in ordered),
        "total_days": total_days,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "storage_warn": bool(storage.get("warn_no_volume")),
        "storage_path": storage.get("path") or "",
    }


def desk_stamp() -> dict[str, Any]:
    from src.desk.items import DESK_QUEUED, normalize_status

    latest = load_latest() or {}
    editorial = load_editorial_items(scope="today")
    open_n = sum(1 for item in editorial if normalize_status(item) == DESK_QUEUED)
    newest = ""
    if editorial:
        newest = max(str(item.get("created_at") or "") for item in editorial)
    return {
        "editorial": len(editorial),
        "open": open_n,
        "latest_at": str(latest.get("updated_at") or ""),
        "pack_id": latest.get("id"),
        "pack_updated_at": str(latest.get("updated_at") or latest.get("created_at") or ""),
        "newest": newest,
        "history_count": editorial_history_count(),
        "next_check": next_check_label(),
    }


def empty_panel_copy(panel: str, *, next_check: str = "", has_pack: bool = False) -> dict[str, str]:
    """Operator-facing empty states — explain why, not just «немає»."""
    check = next_check or next_check_label()
    if panel == "short":
        if has_pack:
            return {"title": "", "body": ""}
        return {
            "title": "Short ще не готовий",
            "body": f"TikTok / IG / Reel з’являться після рендеру. {check}",
        }
    if panel == "tiktok":
        return {
            "title": "Немає Short для TikTok",
            "body": f"Чекаємо ранковий або вечірній пайплайн. {check}",
        }
    if panel == "instagram":
        return {
            "title": "Немає Short для Instagram",
            "body": f"Reel і карусель підтягнуться з паку. {check}",
        }
    if panel == "threads":
        return {
            "title": "Немає постів для Threads",
            "body": (
                "News / snapshot / numbers / reflection з’являться після job. "
                f"Відкриті з учора лишаються тут до 36 год. {check}"
            ),
        }
    if panel == "telegram":
        return {
            "title": "Немає постів для Telegram",
            "body": f"Контекст / digest з’являться з editorial job. {check}",
        }
    return {"title": "Порожньо", "body": check}


def editorial_public_row(item: dict[str, Any]) -> dict[str, Any]:
    """JSON shape for soft-refresh + API."""
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "kind_label": item.get("kind_label") or kind_chip_label(str(item.get("kind") or "")),
        "label": item.get("label"),
        "text": item.get("text"),
        "tab": item.get("tab"),
        "status": item.get("status"),
        "done": bool(item.get("done")),
        "skip_reason": item.get("skip_reason") or "",
        "badge": item.get("badge"),
        "badge_kind": item.get("badge_kind"),
        "is_new": bool(item.get("is_new")),
        "age": item.get("age") or "",
        "snip": item.get("snip") or "",
        "created_at": item.get("created_at") or "",
    }



def write_editorial_items(
    items: list[dict[str, Any]],
    *,
    _locked: bool = False,
) -> None:
    if not _locked:
        with editorial_lock(required=True):
            write_editorial_items(items, _locked=True)
        return

    from src.desk.items import apply_status, normalize_status

    STORAGE.mkdir(parents=True, exist_ok=True)
    now = _now()
    payload_items = []
    for item in items:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        item_id = str(item.get("id") or "").strip() or _stable_editorial_id(text)
        row = apply_status(
            {
                "id": item_id,
                "kind": str(item.get("kind") or "note"),
                "label": str(item.get("label") or item.get("kind") or "Copy"),
                "text": text,
                "created_at": str(item.get("created_at") or now),
                "done": bool(item.get("done")),
                "status": str(item.get("status") or ""),
                "skip_reason": str(item.get("skip_reason") or ""),
            },
            normalize_status(item),
            reason=str(item.get("skip_reason") or ""),
        )
        payload_items.append(row)
    payload = {"updated_at": now, "items": payload_items}
    _editorial_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    db.replace_editorial(payload_items)


def queue_editorial_item(kind: str, label: str, text: str) -> dict[str, Any]:
    """Insert a queued editorial under lock. Idempotent on kind+text id."""
    from datetime import datetime, timezone

    from src.desk.items import DESK_QUEUED, apply_status, normalize_status

    text = (text or "").strip()
    if not text:
        return {"created": False, "reason": "empty"}
    item_id = "e-" + hashlib.sha1(f"{kind}:{text}".encode("utf-8")).hexdigest()[:10]
    with editorial_lock(required=True):
        items = _raw_editorial_items()
        existing = next((item for item in items if item.get("id") == item_id), None)
        if existing:
            status = normalize_status(existing)
            return {
                "id": item_id,
                "created": False,
                "status": status,
                "reason": "dedup",
            }
        items.insert(
            0,
            apply_status(
                {
                    "id": item_id,
                    "kind": kind,
                    "label": label,
                    "text": text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                DESK_QUEUED,
            ),
        )
        write_editorial_items(items, _locked=True)
    return {"id": item_id, "created": True, "status": DESK_QUEUED, "reason": "ok"}


def set_editorial_done(item_id: str, done: bool = True) -> Optional[dict[str, Any]]:
    from src.desk.items import DESK_POSTED, DESK_QUEUED, apply_status

    with editorial_lock(required=True):
        items = _raw_editorial_items()
        found = None
        for index, item in enumerate(items):
            if item.get("id") == item_id:
                found = apply_status(item, DESK_POSTED if done else DESK_QUEUED)
                items[index] = found
                break
        if not found:
            return None
        write_editorial_items(items, _locked=True)
    enriched = next(
        (row for row in load_editorial_items(scope="all") if row.get("id") == item_id),
        None,
    )
    return enriched or found


def set_editorial_skipped(item_id: str, reason: str = "") -> Optional[dict[str, Any]]:
    from src.desk.items import DESK_SKIPPED, apply_status

    with editorial_lock(required=True):
        items = _raw_editorial_items()
        found = None
        for index, item in enumerate(items):
            if item.get("id") == item_id:
                found = apply_status(item, DESK_SKIPPED, reason=reason)
                items[index] = found
                break
        if not found:
            return None
        write_editorial_items(items, _locked=True)
    enriched = next(
        (row for row in load_editorial_items(scope="all") if row.get("id") == item_id),
        None,
    )
    return enriched or found


def pack_day_key(pack: Optional[dict[str, Any]]) -> str:
    if not pack:
        return ""
    return _day_key(str(pack.get("updated_at") or pack.get("created_at") or ""))


def pack_is_today(pack: Optional[dict[str, Any]]) -> bool:
    day = pack_day_key(pack)
    return bool(day) and day == _today_key()


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
    if days == 1:
        return "1 день тому"
    if days < 5:
        return f"{days} дні тому"
    return f"{days} дн тому"


def pack_age_label(pack: Optional[dict[str, Any]]) -> str:
    """Operator-facing age for the latest Short (Ukrainian)."""
    if not pack:
        return ""
    return _age_label(_age_hours(str(pack.get("updated_at") or pack.get("created_at") or "")))


def mark_platforms_posted(
    *,
    short_id: Optional[int] = None,
    video_path: str | Path = "",
    platforms: list[str] | tuple[str, ...] = (),
) -> Optional[dict[str, Any]]:
    """Set desk marks True for auto-posted platforms. No-op if short unknown."""
    sid = int(short_id) if short_id else 0
    if not sid:
        path = str(video_path or "").strip()
        if not path:
            return None
        pack = db.get_short_by_path(path)
        if not pack or not pack.get("id"):
            return None
        sid = int(pack["id"])
    last: Optional[dict[str, Any]] = None
    applied: list[str] = []
    for name in platforms:
        if name not in db.PLATFORMS:
            continue
        updated = db.set_mark(sid, name, True)
        if updated:
            last = updated
            applied.append(name)
    if applied:
        print(f"[desk] marks auto short_id={sid} platforms={','.join(applied)}")
    return last


def desk_metrics() -> dict[str, Any]:
    """Compact ops snapshot for /health and Railway logs."""
    from src.desk.items import DESK_QUEUED, normalize_status

    counts = db.mark_counts()
    latest = load_latest()
    editorial = load_editorial_items(scope="today")
    overdue = overdue_message(editorial, latest)
    return {
        "shorts": counts.get("shorts", 0),
        "posted_youtube": counts.get("youtube", 0),
        "posted_tiktok": counts.get("tiktok", 0),
        "posted_instagram": counts.get("instagram", 0),
        "posted_threads": counts.get("threads", 0),
        "latest_title": (latest or {}).get("title") or "",
        "latest_age": pack_age_label(latest),
        "latest_is_today": pack_is_today(latest),
        "overdue_today": overdue,
        "editorial_open_today": sum(
            1 for item in editorial if normalize_status(item) == DESK_QUEUED
        ),
    }


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
    from src.desk.items import DESK_QUEUED, normalize_status

    threads_new = sum(
        1
        for item in editorial
        if normalize_status(item) == DESK_QUEUED and item.get("tab") != "telegram"
    )
    telegram_new = sum(
        1
        for item in editorial
        if normalize_status(item) == DESK_QUEUED and item.get("tab") == "telegram"
    )
    short_new = 0
    tiktok_new = 0
    ig_new = 0
    # Only badge open Short work for today's pack — stale packs must not hang forever.
    if pack and pack_is_today(pack):
        marks = pack.get("marks") or {}
        if not marks.get("tiktok"):
            tiktok_new = 1
            short_new += 1
        if not marks.get("instagram"):
            ig_new = 1
            short_new += 1
        if not marks.get("youtube"):
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
    from src.desk.items import DESK_POSTED, DESK_QUEUED, normalize_status

    editorial_new = sum(1 for item in editorial if item.get("is_new"))
    editorial_open = sum(
        1 for item in editorial if normalize_status(item) == DESK_QUEUED
    )
    editorial_done = sum(
        1 for item in editorial if normalize_status(item) == DESK_POSTED
    )
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
        "posted_youtube": counts.get("youtube", 0),
        "articles_used": used,
        "pending_youtube": len(pending),
        "latest_title": (latest or {}).get("title") or "",
        "latest_at": _short_ts(str((latest or {}).get("updated_at") or "")),
        "latest_age": pack_age_label(latest),
        "latest_is_today": pack_is_today(latest),
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
        "overdue_today": overdue_message(editorial, latest),
        "metrics": desk_metrics(),
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
                "id": "youtube",
                "label": "YouTube ✓",
                "done": counts.get("youtube", 0),
                "target": max(counts.get("shorts", 0), 1),
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


def overdue_message(editorial: list[dict[str, Any]], latest: Optional[dict[str, Any]]) -> str:
    from src.desk.items import DESK_QUEUED, normalize_status

    bits: list[str] = []
    threads_n = sum(
        1
        for item in editorial
        if normalize_status(item) == DESK_QUEUED and item.get("tab") == "threads"
    )
    tg_n = sum(
        1
        for item in editorial
        if normalize_status(item) == DESK_QUEUED and item.get("tab") == "telegram"
    )
    if threads_n:
        bits.append(f"Threads ×{threads_n}")
    if tg_n:
        bits.append(f"TG ×{tg_n}")
    # Age-gate: do not nag about TikTok/IG/YouTube on yesterday's pack.
    if latest and pack_is_today(latest):
        marks = latest.get("marks") or {}
        if not marks.get("youtube"):
            bits.append("YouTube")
        if not marks.get("tiktok"):
            bits.append("TikTok")
        if not marks.get("instagram"):
            bits.append("IG")
    if not bits:
        return ""
    return "Незапощено сьогодні: " + ", ".join(bits)


def _short_ts(iso: str) -> str:
    return (iso or "")[:16].replace("T", " ")
