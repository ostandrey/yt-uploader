"""Latest Short pack: SQLite + JSON fallback + video folder scan."""

from __future__ import annotations

import json
import shutil
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
    sync_carousel(work_dir)
    saved = db.upsert_short(pack)
    pack.update(saved)
    try:
        from src.desk.push import notify_desk_push

        notify_desk_push(
            "Short ready",
            "TikTok · IG Reel · carousel on desk",
            url="/",
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


def load_editorial_items() -> list[dict[str, Any]]:
    path = STORAGE / "desk_editorial.json"
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
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        out.append(
            {
                "kind": str(item.get("kind") or "note"),
                "label": str(item.get("label") or item.get("kind") or "Copy"),
                "text": text,
            }
        )
    return out[:8]


def write_editorial_items(items: list[dict[str, Any]]) -> None:
    STORAGE.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now(),
        "items": [
            {
                "kind": str(item.get("kind") or "note"),
                "label": str(item.get("label") or item.get("kind") or "Copy"),
                "text": str(item.get("text") or "").strip(),
            }
            for item in items
            if str(item.get("text") or "").strip()
        ][:8],
    }
    (STORAGE / "desk_editorial.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


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
