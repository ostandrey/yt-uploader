"""
Delete old rendered Shorts and workdirs to free disk space.

Keeps JSON state files (dedup, pending uploads). Videos/renders older than
retention_days are removed based on file modification time.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from src.paths import coin_wire_storage, data_root

log = logging.getLogger(__name__)

COIN_WIRE_ROOT = coin_wire_storage()
VIDEOS_DIR = COIN_WIRE_ROOT / "videos"
RENDERS_DIR = COIN_WIRE_ROOT / "renders"

KEEP_RENDER_FILES = frozenset(
    {"metadata.json", "shorts_qa.json", "thumbnail.jpg", "caption.txt"}
)
KEEP_RENDER_DIRS = frozenset({"ig_carousel"})
BUDGET_USED_RATIO = 0.75
MIN_FREE_BYTES = 800 * 1024 * 1024


def _dir_size(path: Path) -> int:
    total = 0
    if path.is_file():
        return path.stat().st_size
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def _fmt_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def disk_usage_for(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "used_ratio": 0.0,
            "total_gb": 0.0,
            "used_gb": 0.0,
            "free_gb": 0.0,
            "used_pct": 0.0,
        }
    total = max(usage.total, 1)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_ratio": usage.used / total,
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "used_pct": round(100 * usage.used / total, 1),
    }


def over_budget(
    path: Path,
    *,
    usage: Optional[dict[str, Any]] = None,
    used_ratio: float = BUDGET_USED_RATIO,
    min_free_bytes: int = MIN_FREE_BYTES,
) -> bool:
    stats = usage or disk_usage_for(path)
    if not stats.get("total_bytes"):
        return False
    return int(stats["free_bytes"]) < min_free_bytes or float(stats["used_ratio"]) >= used_ratio


def cleanup_old_media(
    *,
    retention_days: int = 7,
    root: Path | None = None,
) -> dict:
    """
    Remove videos and matching render folders older than retention_days.

    Returns summary dict with counts and bytes freed.
    """
    if retention_days < 1:
        log.warning("retention_days=%s — cleanup skipped", retention_days)
        return {"skipped": True, "retention_days": retention_days}

    base = root or COIN_WIRE_ROOT
    videos_dir = base / "videos"
    renders_dir = base / "renders"
    cutoff = time.time() - retention_days * 86400

    removed_videos = 0
    removed_renders = 0
    freed_bytes = 0

    if videos_dir.is_dir():
        for video in videos_dir.glob("*.mp4"):
            try:
                if video.stat().st_mtime >= cutoff:
                    continue
                size = _dir_size(video)
                video.unlink(missing_ok=True)
                removed_videos += 1
                freed_bytes += size
                log.info("Removed video: %s (%s)", video.name, _fmt_mb(size))

                render_dir = renders_dir / video.stem
                if render_dir.is_dir():
                    rsize = _dir_size(render_dir)
                    shutil.rmtree(render_dir, ignore_errors=True)
                    removed_renders += 1
                    freed_bytes += rsize
                    log.info("Removed render dir: %s (%s)", render_dir.name, _fmt_mb(rsize))
            except OSError as exc:
                log.warning("Could not remove %s: %s", video, exc)

    if renders_dir.is_dir():
        for render_dir in renders_dir.iterdir():
            if not render_dir.is_dir():
                continue
            try:
                if render_dir.stat().st_mtime >= cutoff:
                    continue
                if (videos_dir / f"{render_dir.name}.mp4").exists():
                    continue
                size = _dir_size(render_dir)
                shutil.rmtree(render_dir, ignore_errors=True)
                removed_renders += 1
                freed_bytes += size
                log.info("Removed orphan render: %s (%s)", render_dir.name, _fmt_mb(rsize))
            except OSError as exc:
                log.warning("Could not remove %s: %s", render_dir, exc)

    summary = {
        "retention_days": retention_days,
        "removed_videos": removed_videos,
        "removed_renders": removed_renders,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
    }
    if removed_videos or removed_renders:
        log.info(
            "Storage cleanup: %d videos, %d render dirs, %s freed",
            removed_videos,
            removed_renders,
            _fmt_mb(freed_bytes),
        )
    else:
        log.info("Storage cleanup: nothing older than %d days", retention_days)
    return summary


def prune_broll_library(*, root: Path | None = None) -> dict:
    """Drop synced B-roll off the volume so desk/history keep disk room.

    Shorts still fetch Pexels/Pixabay live. History SQLite is not touched.
    """
    library = (root or data_root()) / "assets" / "broll_library"
    if not library.is_dir():
        return {"pruned": False, "reason": "no_library", "freed_bytes": 0, "freed_mb": 0}
    size = _dir_size(library)
    shutil.rmtree(library, ignore_errors=True)
    log.info("Pruned B-roll library %s (%s)", library, _fmt_mb(size))
    return {"pruned": True, "freed_bytes": size, "freed_mb": round(size / (1024 * 1024), 1)}


def strip_render_dir(work_dir: Path) -> int:
    """Drop ffmpeg intermediates. Keep desk thumbnail, metadata, carousel."""
    if not work_dir.is_dir():
        return 0
    freed = 0
    for child in list(work_dir.iterdir()):
        if child.is_dir() and child.name in KEEP_RENDER_DIRS:
            continue
        if child.is_file() and child.name in KEEP_RENDER_FILES:
            continue
        try:
            size = _dir_size(child)
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            freed += size
        except OSError as exc:
            log.warning("Could not strip %s: %s", child, exc)
    return freed


def strip_all_renders(*, root: Path | None = None) -> dict:
    renders_dir = (root or COIN_WIRE_ROOT) / "renders"
    stripped = 0
    freed_bytes = 0
    if renders_dir.is_dir():
        for work_dir in renders_dir.iterdir():
            if not work_dir.is_dir():
                continue
            size = strip_render_dir(work_dir)
            if size:
                stripped += 1
                freed_bytes += size
    if freed_bytes:
        log.info("Stripped intermediates from %d render dirs (%s)", stripped, _fmt_mb(freed_bytes))
    return {
        "stripped_dirs": stripped,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
    }


def keep_newest_videos(*, keep: int = 3, root: Path | None = None) -> dict:
    """If the volume is still tight, keep only the newest finished Shorts."""
    if keep < 1:
        keep = 1
    base = root or COIN_WIRE_ROOT
    videos_dir = base / "videos"
    renders_dir = base / "renders"
    if not videos_dir.is_dir():
        return {"removed_videos": 0, "removed_renders": 0, "freed_bytes": 0, "freed_mb": 0}
    videos = sorted(
        [path for path in videos_dir.glob("*.mp4") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed_videos = 0
    removed_renders = 0
    freed_bytes = 0
    for video in videos[keep:]:
        try:
            size = _dir_size(video)
            video.unlink(missing_ok=True)
            removed_videos += 1
            freed_bytes += size
            log.info("Dropped extra video: %s (%s)", video.name, _fmt_mb(size))
            render_dir = renders_dir / video.stem
            if render_dir.is_dir():
                rsize = _dir_size(render_dir)
                shutil.rmtree(render_dir, ignore_errors=True)
                removed_renders += 1
                freed_bytes += rsize
        except OSError as exc:
            log.warning("Could not drop %s: %s", video, exc)
    return {
        "removed_videos": removed_videos,
        "removed_renders": removed_renders,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
        "kept": min(keep, len(videos)),
    }


def reclaim_volume(
    *,
    retention_days: int = 7,
    keep_latest_videos: int = 3,
    root: Path | None = None,
    data: Path | None = None,
    usage: Optional[dict[str, Any]] = None,
) -> dict:
    """Prune B-roll, strip render leftovers, then age-out old Shorts.

    If the volume is still over budget, keep only the newest few MP4s.
    Desk SQLite / push subs are never deleted.
    """
    data_path = data or data_root()
    storage_root = root or COIN_WIRE_ROOT
    before = usage or disk_usage_for(data_path)
    pruned = prune_broll_library(root=data_path)
    stripped = strip_all_renders(root=storage_root)
    cleaned = cleanup_old_media(retention_days=retention_days, root=storage_root)
    emergency = {"removed_videos": 0, "removed_renders": 0, "freed_bytes": 0, "freed_mb": 0}
    after = disk_usage_for(data_path)
    if over_budget(data_path, usage=after):
        emergency = keep_newest_videos(keep=keep_latest_videos, root=storage_root)
        after = disk_usage_for(data_path)
        if over_budget(data_path, usage=after):
            log.warning(
                "Volume still tight after reclaim: %.1f%% used, %.2f GB free",
                after.get("used_pct") or 0,
                after.get("free_gb") or 0,
            )
    freed = (
        int(pruned.get("freed_bytes") or 0)
        + int(stripped.get("freed_bytes") or 0)
        + int(cleaned.get("freed_bytes") or 0)
        + int(emergency.get("freed_bytes") or 0)
    )
    log.info(
        "Volume reclaim: %s freed (broll=%s renders=%s old=%s extra=%s) now %.1f%%",
        _fmt_mb(freed),
        _fmt_mb(int(pruned.get("freed_bytes") or 0)),
        _fmt_mb(int(stripped.get("freed_bytes") or 0)),
        _fmt_mb(int(cleaned.get("freed_bytes") or 0)),
        _fmt_mb(int(emergency.get("freed_bytes") or 0)),
        after.get("used_pct") or 0,
    )
    return {
        "before": before,
        "after": after,
        "pruned": pruned,
        "stripped": stripped,
        "cleaned": cleaned,
        "emergency": emergency,
        "freed_bytes": freed,
        "freed_mb": round(freed / (1024 * 1024), 1),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Remove old Coin Wire videos and render dirs")
    parser.add_argument("--days", type=int, default=7, help="Delete files older than N days")
    parser.add_argument("--keep", type=int, default=3, help="Keep newest N videos if still full")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    reclaim_volume(retention_days=args.days, keep_latest_videos=args.keep)


if __name__ == "__main__":
    main()
