"""Worker → desk heartbeat for /health (separate Railway processes)."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.paths import coin_wire_storage

STATE_FILE = coin_wire_storage() / "scheduler_state.json"
LOCK_FILE = coin_wire_storage() / "scheduler_state.lock"

# Short job hard timeout is 50m; treat longer "running" as stale after kill.
STALE_RUNNING_SEC = int(os.getenv("SCHEDULER_STALE_RUNNING_SEC", str(55 * 60)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@contextmanager
def _file_lock(timeout_sec: float = 8.0, *, required: bool = False) -> Iterator[None]:
    """Cross-process lock so concurrent jobs don't clobber scheduler_state.json."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+", encoding="utf-8")
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
                            f"scheduler_state.lock busy >{timeout_sec}s"
                        ) from None
                    # Reads may proceed unlocked; writers should pass required=True.
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
        handle.close()


def _load_unlocked() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"jobs": {}, "updated_at": ""}
    try:
        loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {"jobs": {}, "updated_at": ""}
    except (OSError, json.JSONDecodeError):
        return {"jobs": {}, "updated_at": ""}


def _write_unlocked(data: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(STATE_FILE)


def mark_job(job_id: str, status: str, **extra: Any) -> None:
    """status: running | ok | failed | scheduled"""
    with _file_lock(required=True):
        data = _load_unlocked()
        jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
        row = dict(jobs.get(job_id) or {})
        row["status"] = status
        row["updated_at"] = _now()
        if status == "running":
            row["last_started_at"] = _now()
            row["is_running"] = True
        else:
            # Always clear running on terminal states (incl. after killpg timeout).
            row["is_running"] = False
            row["last_finished_at"] = _now()
            row["last_ok"] = status == "ok"
        row.update({k: v for k, v in extra.items() if v is not None})
        jobs[job_id] = row
        data["jobs"] = jobs
        data["updated_at"] = _now()
        _write_unlocked(data)


def write_schedule(jobs: dict[str, dict[str, Any]]) -> None:
    """Persist next_run hints from the worker at boot."""
    with _file_lock(required=True):
        data = _load_unlocked()
        existing = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
        for job_id, meta in jobs.items():
            row = dict(existing.get(job_id) or {})
            # Never clobber a live run with boot schedule defaults.
            live = bool(row.get("is_running")) and str(row.get("status") or "") == "running"
            preserved = {
                "is_running": row.get("is_running"),
                "status": row.get("status"),
                "last_started_at": row.get("last_started_at"),
                "last_finished_at": row.get("last_finished_at"),
                "last_ok": row.get("last_ok"),
            }
            row.update(meta)
            row.setdefault("status", "scheduled")
            if live:
                row["is_running"] = True
                row["status"] = "running"
                if preserved.get("last_started_at"):
                    row["last_started_at"] = preserved["last_started_at"]
            else:
                row.setdefault("is_running", False)
            existing[job_id] = row
        data["jobs"] = existing
        data["updated_at"] = _now()
        _write_unlocked(data)


def _apply_stale(jobs: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    out: dict[str, Any] = {}
    for job_id, row in jobs.items():
        if not isinstance(row, dict):
            continue
        fixed = dict(row)
        if fixed.get("is_running"):
            started = _parse_iso(str(fixed.get("last_started_at") or ""))
            age = (now - started).total_seconds() if started else None
            # Missing start timestamp still ages out via updated_at.
            if age is None:
                updated = _parse_iso(str(fixed.get("updated_at") or ""))
                age = (now - updated).total_seconds() if updated else STALE_RUNNING_SEC + 1
            if age is not None and age > STALE_RUNNING_SEC:
                fixed["is_running"] = False
                fixed["status"] = "stale"
                fixed["stale"] = True
                fixed["stale_after_sec"] = int(age)
        out[job_id] = fixed
    return out


def read_state() -> dict[str, Any]:
    with _file_lock():
        data = _load_unlocked()
    jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    data = dict(data)
    data["jobs"] = _apply_stale(jobs)
    return data
