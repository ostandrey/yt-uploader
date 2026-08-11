"""SQLite for desk shorts + posted marks. One operator, one file on the volume."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "data" / "storage" / "coin_wire"
PLATFORMS = ("tiktok", "instagram", "threads")

_lock = threading.RLock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS shorts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    ig_caption TEXT NOT NULL DEFAULT '',
    threads_text TEXT NOT NULL DEFAULT '',
    youtube_url TEXT NOT NULL DEFAULT '',
    work_dir TEXT NOT NULL DEFAULT '',
    qa_score INTEGER,
    bytes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS marks (
    short_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    PRIMARY KEY (short_id, platform),
    FOREIGN KEY (short_id) REFERENCES shorts(id)
);
CREATE INDEX IF NOT EXISTS idx_shorts_updated ON shorts(updated_at);
"""


def db_path() -> Path:
    override = os.getenv("DESK_DB", "").strip()
    if override:
        return Path(override)
    return STORAGE / "desk.sqlite"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    global _initialized
    if not _initialized:
        with _lock:
            if not _initialized:
                conn.executescript(SCHEMA)
                conn.commit()
                _initialized = True
    return conn


def reset_init_for_tests() -> None:
    global _initialized
    _initialized = False


def upsert_short(pack: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    video_path = str(pack["video_path"])
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO shorts (
                    video_path, title, ig_caption, threads_text, youtube_url,
                    work_dir, qa_score, bytes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_path) DO UPDATE SET
                    title=excluded.title,
                    ig_caption=excluded.ig_caption,
                    threads_text=excluded.threads_text,
                    youtube_url=excluded.youtube_url,
                    work_dir=excluded.work_dir,
                    qa_score=excluded.qa_score,
                    bytes=excluded.bytes,
                    updated_at=excluded.updated_at
                """,
                (
                    video_path,
                    pack.get("title") or "",
                    pack.get("ig_caption") or "",
                    pack.get("threads_text") or "",
                    pack.get("youtube_url") or "",
                    pack.get("work_dir") or "",
                    pack.get("qa_score"),
                    int(pack.get("bytes") or 0),
                    now,
                    now,
                ),
            )
            conn.commit()
            return get_short_by_path(video_path) or pack
        finally:
            conn.close()


def get_short_by_path(video_path: str) -> Optional[dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM shorts WHERE video_path = ?", (video_path,)
        ).fetchone()
        if not row:
            return None
        return _hydrate(conn, row)
    finally:
        conn.close()


def _hydrate(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    marks = {name: False for name in PLATFORMS}
    posted: dict[str, Optional[str]] = {name: None for name in PLATFORMS}
    for mark in conn.execute(
        "SELECT platform, posted_at FROM marks WHERE short_id = ?",
        (row["id"],),
    ):
        marks[str(mark["platform"])] = True
        posted[str(mark["platform"])] = mark["posted_at"]
    pack = {key: row[key] for key in row.keys()}
    pack["marks"] = marks
    pack["posted_at"] = posted
    return pack


def latest_short() -> Optional[dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM shorts ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return _hydrate(conn, row)
    finally:
        conn.close()


def list_shorts(limit: int = 20) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM shorts ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_hydrate(conn, row) for row in rows]
    finally:
        conn.close()


def set_mark(short_id: int, platform: str, posted: bool) -> Optional[dict[str, Any]]:
    if platform not in PLATFORMS:
        raise ValueError("unknown platform")
    with _lock:
        conn = connect()
        try:
            exists = conn.execute(
                "SELECT id FROM shorts WHERE id = ?", (short_id,)
            ).fetchone()
            if not exists:
                return None
            if posted:
                conn.execute(
                    """
                    INSERT INTO marks (short_id, platform, posted_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(short_id, platform) DO UPDATE SET posted_at=excluded.posted_at
                    """,
                    (short_id, platform, _now()),
                )
            else:
                conn.execute(
                    "DELETE FROM marks WHERE short_id = ? AND platform = ?",
                    (short_id, platform),
                )
            conn.commit()
            row = conn.execute("SELECT * FROM shorts WHERE id = ?", (short_id,)).fetchone()
            return _hydrate(conn, row) if row else None
        finally:
            conn.close()


def mark_counts() -> dict[str, int]:
    conn = connect()
    try:
        counts = {name: 0 for name in PLATFORMS}
        for row in conn.execute(
            "SELECT platform, COUNT(*) AS n FROM marks GROUP BY platform"
        ):
            counts[str(row["platform"])] = int(row["n"])
        total = conn.execute("SELECT COUNT(*) AS n FROM shorts").fetchone()["n"]
        return {"shorts": int(total), **counts}
    finally:
        conn.close()
