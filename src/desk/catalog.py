"""Latest Short pack: SQLite + JSON fallback + video folder scan."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.desk import db

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "data" / "storage" / "coin_wire"
VIDEOS_DIR = STORAGE / "videos"
LATEST_FILE = STORAGE / "desk_latest.json"
HISTORY_FILE = STORAGE / "desk_history.json"
PENDING_FILE = STORAGE / "pending_uploads.json"
USED_FILE = STORAGE / "used_short_articles.json"


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
) -> dict[str, Any]:
    video_path = Path(video_path)
    pack = {
        "title": title.strip(),
        "ig_caption": (ig_caption or "").strip(),
        "threads_text": (threads_text or "").strip(),
        "youtube_url": (youtube_url or "").strip(),
        "video_path": str(video_path),
        "work_dir": str(work_dir),
        "updated_at": _now(),
        "qa_score": qa_score,
        "bytes": video_path.stat().st_size if video_path.is_file() else 0,
    }
    STORAGE.mkdir(parents=True, exist_ok=True)
    LATEST_FILE.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    saved = db.upsert_short(pack)
    pack.update(saved)
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
    }


def _short_ts(iso: str) -> str:
    return (iso or "")[:16].replace("T", " ")
