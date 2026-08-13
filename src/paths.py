"""Persistent data roots for Coin Wire (Railway volume = /app/data)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def data_root() -> Path:
    """Persistent data dir. Railway volume must cover this path (usually /app/data)."""
    override = os.getenv("COIN_WIRE_DATA", "").strip()
    if override:
        path = Path(override)
    elif os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
        path = Path("/app/data")
    else:
        path = ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def coin_wire_storage() -> Path:
    return data_root() / "storage" / "coin_wire"


def storage_status() -> dict:
    """Counts for ops /health — empty after redeploy usually means no volume."""
    storage = coin_wire_storage()
    sqlite = storage / "desk.sqlite"
    editorial = storage / "desk_editorial.json"
    latest = storage / "desk_latest.json"
    videos = storage / "videos"
    subs = storage / "desk_push_subs.json"
    video_n = 0
    if videos.is_dir():
        video_n = sum(1 for p in videos.glob("*.mp4") if p.is_file())
    sub_n = 0
    if subs.is_file():
        try:
            import json

            data = json.loads(subs.read_text(encoding="utf-8"))
            items = data.get("subscriptions") if isinstance(data, dict) else data
            sub_n = len(items) if isinstance(items, list) else 0
        except (OSError, json.JSONDecodeError, TypeError):
            sub_n = 0
    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
    root = data_root()
    vol_env = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    mounted = _path_is_persistent(root) if on_railway else True
    return {
        "path": str(storage),
        "data_root": str(root),
        "sqlite": sqlite.is_file(),
        "latest": latest.is_file(),
        "editorial": editorial.is_file(),
        "videos": video_n,
        "push_subs": sub_n,
        "railway": on_railway,
        "coin_wire_data": os.getenv("COIN_WIRE_DATA", ""),
        "volume_env": vol_env,
        "volume_mounted": mounted,
        "warn_no_volume": on_railway and not mounted,
    }


def _path_is_persistent(path: Path) -> bool:
    """True if Railway volume covers this directory (env, ismount, or /proc)."""
    try:
        target = path.resolve()
    except OSError:
        target = path
    vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if vol:
        try:
            mount = Path(vol).resolve()
        except OSError:
            mount = Path(vol)
        name = mount.name.lower()
        if name not in {"tokens", "token"}:
            try:
                if target == mount or target.is_relative_to(mount):
                    return True
            except (OSError, ValueError):
                pass
    cursor = target
    for _ in range(8):
        if cursor == Path("/"):
            break
        if os.path.ismount(str(cursor)):
            return True
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return _proc_covers(target)


def _proc_covers(target: Path) -> bool:
    try:
        mounts = Path("/proc/mounts").read_text(encoding="utf-8")
    except OSError:
        return False
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        mount_s = parts[1].encode("utf-8").decode("unicode_escape")
        try:
            mount = Path(mount_s).resolve()
        except OSError:
            continue
        if mount == Path("/"):
            continue
        try:
            if target == mount or target.is_relative_to(mount):
                return True
        except (OSError, ValueError):
            continue
    return False
