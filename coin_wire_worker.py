#!/usr/bin/env python3
"""
Coin Wire background worker — runs on Railway or any always-on server.

Schedule (see config/coin_wire.yaml, default America/New_York):
  Telegram news  — smart poll every 30 min (3–8/day, breaking ASAP)
  YouTube Shorts — 09:00, 18:00 (unlisted upload + Telegram notify)

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
)
log = logging.getLogger("coin_wire_worker")


def _load_config() -> dict:
    config_path = ROOT / "config" / "coin_wire.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _run_script(script: str, *args: str) -> bool:
    cmd = [PYTHON, str(ROOT / script), *args]
    label = script.replace("_", " ")
    log.info("Running %s ...", label)
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("  %s", line)
    if result.returncode != 0:
        log.error("FAILED %s (%s): %s", label, result.returncode, result.stderr.strip())
        return False
    log.info("OK: %s", label)
    return True


def job_telegram() -> None:
    _run_script("post_crypto_news.py")


def job_short() -> None:
    _run_script("run_coin_wire_pipeline.py")


def job_cleanup() -> None:
    from src.storage_cleanup import cleanup_old_media

    config = _load_config()
    storage = config.get("automation", {}).get("storage", {})
    retention_days = int(storage.get("retention_days", 7))
    cleanup_old_media(retention_days=retention_days)


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


def main() -> None:
    load_dotenv(ROOT / ".env")
    _preflight()
    config = _load_config()
    automation = config.get("automation", {})
    storage_cfg = automation.get("storage", {})
    retention_days = int(storage_cfg.get("retention_days", 7))

    from src.storage_cleanup import cleanup_old_media

    cleanup_old_media(retention_days=retention_days)

    schedule_cfg = automation.get("schedule", {})
    timezone = automation.get("timezone", "UTC")
    tg_poll_minutes = int(
        config.get("publishing", {}).get("telegram", {}).get("poll_interval_minutes", 30)
    )

    short_times: list[str] = schedule_cfg.get("shorts", ["10:00", "18:00"])
    floor_times: list[str] = schedule_cfg.get(
        "telegram_floor", schedule_cfg.get("telegram", ["08:00", "12:00", "17:00"])
    )
    storage_cfg = automation.get("storage", {})
    cleanup_time: str = storage_cfg.get("cleanup_time", "03:00")
    tg_cfg = config.get("publishing", {}).get("telegram", {})

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

    log.info("Worker ready at %s", datetime.now().isoformat())

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped.")


if __name__ == "__main__":
    main()
