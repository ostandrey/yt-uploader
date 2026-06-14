#!/usr/bin/env python3
"""
Coin Wire background worker — runs on Railway or any always-on server.

Schedule (UTC by default, see config/coin_wire.yaml):
  Telegram news  — 08:00, 14:00, 20:00
  YouTube Shorts — 10:00, 18:00 (auto-scored serious news, unlisted upload)

Usage:
    python coin_wire_worker.py

Railway:
    Set start command to: python coin_wire_worker.py
    Mount volume at /app/data and /app/tokens for persistence.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

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
    _run_script("post_crypto_news.py", "--count", "1")


def job_short() -> None:
    _run_script("run_coin_wire_pipeline.py")


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    hour, minute = time_str.strip().split(":")
    return int(hour), int(minute)


def main() -> None:
    load_dotenv(ROOT / ".env")
    config = _load_config()
    automation = config.get("automation", {})
    schedule_cfg = automation.get("schedule", {})
    timezone = automation.get("timezone", "UTC")

    tg_times: list[str] = schedule_cfg.get("telegram", ["08:00", "14:00", "20:00"])
    short_times: list[str] = schedule_cfg.get("shorts", ["10:00", "18:00"])

    log.info("=" * 60)
    log.info("Coin Wire Worker — starting")
    log.info("Timezone: %s", timezone)
    log.info("Telegram: %s", ", ".join(tg_times))
    log.info("Shorts:   %s", ", ".join(short_times))
    log.info("News filter: min score %s, max age %sh",
             config.get("content", {}).get("filters", {}).get("short_min_score", 12),
             config.get("content", {}).get("filters", {}).get("short_max_age_hours", 24))
    log.info("=" * 60)

    scheduler = BlockingScheduler(timezone=timezone)

    for index, time_str in enumerate(tg_times):
        hour, minute = _parse_hhmm(time_str)
        scheduler.add_job(
            job_telegram,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            id=f"telegram_{index}",
            replace_existing=True,
            misfire_grace_time=3600,
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

    log.info("Worker ready at %s", datetime.now().isoformat())

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker stopped.")


if __name__ == "__main__":
    main()
