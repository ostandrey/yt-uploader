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

log = logging.getLogger(__name__)

COIN_WIRE_ROOT = Path(__file__).resolve().parents[1] / "data" / "storage" / "coin_wire"
VIDEOS_DIR = COIN_WIRE_ROOT / "videos"
RENDERS_DIR = COIN_WIRE_ROOT / "renders"


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
                log.info("Removed orphan render: %s (%s)", render_dir.name, _fmt_mb(size))
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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Remove old Coin Wire videos and render dirs")
    parser.add_argument("--days", type=int, default=7, help="Delete files older than N days")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cleanup_old_media(retention_days=args.days)


if __name__ == "__main__":
    main()
