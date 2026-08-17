#!/usr/bin/env python3
"""
Coin Wire background worker — runs on Railway or any always-on server.

Schedule (see config/coin_wire.yaml, default America/New_York):
  Telegram news  — smart poll every 30 min (3–8/day, breaking ASAP)
  YouTube Shorts — 09:00, 18:00 (unlisted upload, auto-publish after delay)
  TG weekly digest — Monday 09:00
  Threads recap — Friday 18:00
  TG polls — Wednesday/Friday 12:00

Usage:
    python coin_wire_worker.py

Railway:
    Set start command to: python coin_wire_worker.py
    Mount volume at /app/data and /app/tokens for persistence.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
TOKEN_FILE = ROOT / "tokens" / "coin_wire_token.json"

REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "YOUTUBE_CRYPTO_CLIENT_ID",
    "YOUTUBE_CRYPTO_CLIENT_SECRET",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("coin_wire_worker")


def _load_config() -> dict:
    config_path = ROOT / "config" / "coin_wire.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _run_script(script: str, *args: str, quiet_ok: bool = False) -> bool:
    cmd = [PYTHON, str(ROOT / script), *args]
    label = script.replace("_", " ")
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "LANG": "C.UTF-8",
    }
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    stdout = (result.stdout or "").strip()
    failed = result.returncode != 0
    if not quiet_ok or stdout or failed:
        log.info("Running %s ...", label)
        for line in stdout.splitlines():
            log.info("  %s", line)
    if failed:
        log.error("FAILED %s (%s): %s", label, result.returncode, result.stderr.strip())
        return False
    if not quiet_ok or stdout:
        log.info("OK: %s", label)
    return True


def job_telegram() -> None:
    _run_script("post_crypto_news.py")


def job_short() -> None:
    _run_script("run_coin_wire_pipeline.py")


def job_publish_pending() -> None:
    _run_script("publish_pending_shorts.py")


def job_telegram_bot() -> None:
    _run_script("poll_telegram_commands.py", quiet_ok=True)


def job_weekly_digest() -> None:
    _run_script("post_editorial.py", "--weekly-digest")


def job_threads_recap() -> None:
    _run_script("post_editorial.py", "--threads-recap")


def job_market_snapshot() -> None:
    _run_script("post_editorial.py", "--market-snapshot")


def job_telegram_poll() -> None:
    _run_script("post_editorial.py", "--poll")


def _refresh_latest_carousel() -> None:
    """Re-render desk carousel from the last Short so old duplicate slides update."""
    import json

    from src.desk.catalog import load_latest, sync_carousel, sync_story
    from src.media.ig_carousel import render_what_moved
    from src.paths import coin_wire_storage

    pack = load_latest()
    if not pack:
        log.info("Carousel refresh: no latest Short on desk")
        return
    work = Path(str(pack.get("work_dir") or ""))
    meta: dict = {}
    if work.is_dir() and (work / "metadata.json").is_file():
        try:
            meta = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    title = str(pack.get("title") or meta.get("title") or "").strip()
    if not title:
        log.info("Carousel refresh: latest pack has no title")
        return
    out_dir = work if work.is_dir() else coin_wire_storage() / "renders" / "carousel_refresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = render_what_moved(
        {
            "title": title,
            "description": str(meta.get("description") or ""),
            "script": str(meta.get("script") or ""),
            "source_link": str(meta.get("source_link") or ""),
            "allow_quote_card": False,
        },
        out_dir,
        fetch_stock=False,
    )
    sync_carousel(out_dir)
    sync_story(out_dir)
    log.info("Carousel refresh: %d slides for %s", len(paths), title[:60])


def job_cleanup() -> None:
    from src.storage_cleanup import reclaim_volume

    config = _load_config()
    storage = config.get("automation", {}).get("storage", {})
    reclaim_volume(
        retention_days=int(storage.get("retention_days", 7)),
        keep_latest_videos=int(storage.get("keep_latest_videos", 3)),
    )


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    hour, minute = time_str.strip().split(":")
    return int(hour), int(minute)


def _bootstrap_youtube_token() -> None:
    """Write OAuth token from env on first deploy (Railway secret)."""
    token_json = os.getenv("YOUTUBE_CRYPTO_TOKEN_JSON", "").strip()
    if not token_json or TOKEN_FILE.exists():
        return
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token_json, encoding="utf-8")
    log.info("YouTube token bootstrapped from YOUTUBE_CRYPTO_TOKEN_JSON")


def _preflight() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    _bootstrap_youtube_token()

    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "YouTube token missing. On Railway set YOUTUBE_CRYPTO_TOKEN_JSON "
            "(contents of tokens/coin_wire_token.json) or mount a volume at /app/tokens."
        )

    pexels = os.getenv("PEXELS_API_KEY", "")
    pixabay = os.getenv("PIXABAY_API_KEY", "")
    if not pexels and not pixabay:
        log.warning("No PEXELS_API_KEY or PIXABAY_API_KEY — stock footage may be limited")

    from src.paths import storage_status

    st = storage_status()
    disk = st.get("disk") or {}
    log.info(
        "Storage %s | sqlite=%s videos=%s editorial=%s push_subs=%s | disk %s%% (%s/%s GB)",
        st["path"],
        st["sqlite"],
        st["videos"],
        st["editorial"],
        st["push_subs"],
        disk.get("used_pct", "?"),
        disk.get("used_gb", "?"),
        disk.get("total_gb", "?"),
    )
    if st.get("warn_no_volume"):
        log.warning(
            "Desk storage looks empty on Railway — mount a persistent volume at "
            "/app/data (or set COIN_WIRE_DATA). Without it, history / Shorts / "
            "push subscriptions wipe on every deploy."
        )

def _sync_broll_background() -> None:
    """R2 pull can take minutes — never block PORT / Railway health on it."""

    def run() -> None:
        try:
            from src.media.broll_sync import ensure_library_on_start

            ensure_library_on_start()
        except Exception as exc:
            log.warning("B-roll sync failed (will fall back to live Pexels): %s", exc)

    threading.Thread(target=run, name="broll-sync", daemon=True).start()


def main() -> None:
    load_dotenv(ROOT / ".env")
    # Bind PORT before any slow I/O so Railway healthcheck does not 502.
    try:
        from src.desk.server import start_desk_thread

        start_desk_thread()
    except Exception as exc:
        log.warning("Desk did not start: %s", exc)

    _preflight()
    config = _load_config()
    automation = config.get("automation", {})
    storage_cfg = automation.get("storage", {})
    retention_days = int(storage_cfg.get("retention_days", 7))
    keep_latest = int(storage_cfg.get("keep_latest_videos", 3))

    from src.storage_cleanup import reclaim_volume

    try:
        reclaimed = reclaim_volume(
            retention_days=retention_days,
            keep_latest_videos=keep_latest,
        )
        if reclaimed.get("freed_mb"):
            log.info("Freed %s MB from volume on start", reclaimed.get("freed_mb"))
    except Exception as exc:
        log.warning("Volume reclaim skipped: %s", exc)

    try:
        _refresh_latest_carousel()
    except Exception as exc:
        log.warning("Carousel refresh skipped: %s", exc)

    _sync_broll_background()

    schedule_cfg = automation.get("schedule", {})
    timezone = automation.get("timezone", "UTC")
    tg_poll_minutes = int(
        config.get("publishing", {}).get("telegram", {}).get("poll_interval_minutes", 30)
    )

    short_times: list[str] = schedule_cfg.get("shorts", ["10:00", "18:00"])
    floor_times: list[str] = schedule_cfg.get(
        "telegram_floor", schedule_cfg.get("telegram", ["08:00", "12:00", "17:00"])
    )
    cleanup_time: str = storage_cfg.get("cleanup_time", "03:00")
    tg_cfg = config.get("publishing", {}).get("telegram", {})
    yt_cfg = config.get("publishing", {}).get("youtube", {})
    from src.publishers.pending_publish import auto_publish_enabled

    auto_pub = auto_publish_enabled(config)
    pub_poll = int(yt_cfg.get("publish_poll_minutes", 5))
    bot_poll = int(yt_cfg.get("bot_poll_seconds", 20))

    log.info("=" * 60)
    log.info("Coin Wire Worker — starting")
    log.info("Timezone: %s", timezone)
    log.info(
        "Telegram: every %dm, %d–%d posts/day, floor %s",
        tg_poll_minutes,
        tg_cfg.get("min_posts_per_day", 3),
        tg_cfg.get("max_posts_per_day", 8),
        ", ".join(floor_times),
    )
    log.info("Shorts:   %s", ", ".join(short_times))
    log.info(
        "Publish:  auto=%s, delay %dm, poll every %dm, bot every %ds",
        "ON" if auto_pub else "OFF",
        yt_cfg.get("auto_publish_delay_minutes", 30),
        pub_poll,
        bot_poll,
    )
    log.info("Cleanup:  %s (retain %d days)", cleanup_time, retention_days)
    log.info("News filter: min score %s, max age %sh",
             config.get("content", {}).get("filters", {}).get("short_min_score", 12),
             config.get("content", {}).get("filters", {}).get("short_max_age_hours", 24))
    log.info("=" * 60)

    scheduler = BlockingScheduler(timezone=timezone)

    scheduler.add_job(
        job_telegram,
        IntervalTrigger(minutes=tg_poll_minutes),
        id="telegram_smart",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        job_publish_pending,
        IntervalTrigger(minutes=pub_poll),
        id="youtube_auto_publish",
        replace_existing=True,
        misfire_grace_time=600,
    )

    scheduler.add_job(
        job_telegram_bot,
        IntervalTrigger(seconds=bot_poll),
        id="telegram_bot_commands",
        replace_existing=True,
        misfire_grace_time=30,
    )

    for index, time_str in enumerate(short_times):
        hour, minute = _parse_hhmm(time_str)
        scheduler.add_job(
            job_short,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            id=f"short_{index}",
            replace_existing=True,
            misfire_grace_time=7200,
        )

    cleanup_hour, cleanup_minute = _parse_hhmm(cleanup_time)
    scheduler.add_job(
        job_cleanup,
        CronTrigger(hour=cleanup_hour, minute=cleanup_minute, timezone=timezone),
        id="storage_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    editorial_cfg = config.get("publishing", {}).get("editorial", {}) or {}
    digest_time = schedule_cfg.get("weekly_digest", "09:00")
    recap_time = schedule_cfg.get("threads_recap", "18:00")
    poll_times: list[str] = schedule_cfg.get("telegram_poll_times", ["12:00"])
    if editorial_cfg.get("weekly_digest", True):
        hour, minute = _parse_hhmm(digest_time)
        scheduler.add_job(
            job_weekly_digest,
            CronTrigger(day_of_week="mon", hour=hour, minute=minute, timezone=timezone),
            id="weekly_digest",
            replace_existing=True,
            misfire_grace_time=7200,
        )
        log.info("Weekly digest: Monday %s", digest_time)
    if editorial_cfg.get("threads_recap", True):
        hour, minute = _parse_hhmm(recap_time)
        scheduler.add_job(
            job_threads_recap,
            CronTrigger(day_of_week="fri", hour=hour, minute=minute, timezone=timezone),
            id="threads_recap",
            replace_existing=True,
            misfire_grace_time=7200,
        )
        log.info("Threads recap: Friday %s", recap_time)
    snapshot_time = schedule_cfg.get("market_snapshot", "08:00")
    if editorial_cfg.get("market_snapshot", True):
        hour, minute = _parse_hhmm(snapshot_time)
        scheduler.add_job(
            job_market_snapshot,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            id="market_snapshot",
            replace_existing=True,
            misfire_grace_time=7200,
        )
        log.info("Market snapshot: daily %s", snapshot_time)
    if int(editorial_cfg.get("poll_per_week", 0) or 0) > 0:
        for index, time_str in enumerate(poll_times):
            hour, minute = _parse_hhmm(time_str)
            scheduler.add_job(
                job_telegram_poll,
                CronTrigger(
                    day_of_week="wed,fri",
                    hour=hour,
                    minute=minute,
                    timezone=timezone,
                ),
                id=f"telegram_poll_{index}",
                replace_existing=True,
                misfire_grace_time=7200,
            )
        log.info("Telegram polls: Wed/Fri %s", ", ".join(poll_times))

    log.info("Worker ready at %s", datetime.now().isoformat())
    log.info(
        "Real jobs log as post_crypto_news / run_coin_wire_pipeline / post_editorial. "
        "Telegram bot poll is silent unless you send a command."
    )
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped.")


if __name__ == "__main__":
    main()
