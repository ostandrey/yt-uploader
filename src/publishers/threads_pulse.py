"""
Queue Threads-ready news copy after Telegram publishes a strong story.

Operator posts manually from the desk PWA. Graph auto-post is off by default
(desk_only=true) — there is no reliable posting API for this workflow.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from src.content.threads_pulse import build_threads_news_pulse, tier_meets_minimum
from src.paths import coin_wire_storage

log = logging.getLogger(__name__)

STATE_FILE = coin_wire_storage() / "threads_daily_state.json"


@dataclass
class ThreadsPulseConfig:
    enabled: bool = True
    desk_only: bool = True
    min_tier: str = "strong"  # strong | insight | breaking
    max_per_day: int = 3
    cooldown_minutes: int = 120
    question_rate: float = 0.0
    timezone: str = "America/New_York"
    skip_if_short_used: bool = False

    @classmethod
    def from_config(cls, config: dict) -> "ThreadsPulseConfig":
        threads = config.get("publishing", {}).get("threads", {})
        pulse = threads.get("news_pulse", {})
        automation = config.get("automation", {})
        # Prefer explicit desk_only. Graph only when desk_only is false
        # (optional auto_publish escape hatch must not override desk_only=true).
        if "desk_only" in pulse:
            desk_only = bool(pulse.get("desk_only"))
        elif "auto_publish" in pulse:
            desk_only = not bool(pulse.get("auto_publish"))
        else:
            desk_only = True
        return cls(
            enabled=bool(pulse.get("enabled", True)),
            desk_only=bool(desk_only),
            min_tier=str(pulse.get("min_tier", "strong")),
            max_per_day=int(pulse.get("max_per_day", 3)),
            cooldown_minutes=int(pulse.get("cooldown_minutes", 120)),
            question_rate=float(pulse.get("question_rate", 0)),
            timezone=automation.get("timezone", "America/New_York"),
            skip_if_short_used=bool(pulse.get("skip_if_short_used", False)),
        )


@dataclass
class ThreadsDailyState:
    date: str
    post_count: int = 0
    last_post_at: Optional[str] = None
    posted_hashes: list[str] = field(default_factory=list)

    @classmethod
    def for_today(cls, tz_name: str) -> "ThreadsDailyState":
        today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
        return cls(date=today, post_count=0, posted_hashes=[])


def load_threads_state(path: Path, tz_name: str) -> ThreadsDailyState:
    today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    if not path.exists():
        return ThreadsDailyState.for_today(tz_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("date") != today:
            return ThreadsDailyState.for_today(tz_name)
        return ThreadsDailyState(
            date=today,
            post_count=int(data.get("post_count", 0)),
            last_post_at=data.get("last_post_at"),
            posted_hashes=list(data.get("posted_hashes", [])),
        )
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return ThreadsDailyState.for_today(tz_name)


def save_threads_state(path: Path, state: ThreadsDailyState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "date": state.date,
                "post_count": state.post_count,
                "last_post_at": state.last_post_at,
                "posted_hashes": state.posted_hashes[-50:],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _minutes_since_last(state: ThreadsDailyState, tz_name: str) -> Optional[float]:
    if not state.last_post_at:
        return None
    last = datetime.fromisoformat(state.last_post_at)
    if last.tzinfo is None:
        last = last.replace(tzinfo=ZoneInfo(tz_name))
    now = datetime.now(ZoneInfo(tz_name))
    return (now - last).total_seconds() / 60


def maybe_post_news_pulse(
    article: Dict,
    tier: str,
    cfg: ThreadsPulseConfig,
    *,
    state_path: Path = STATE_FILE,
    dry_run: bool = False,
) -> dict:
    """
    Build Threads news copy after Telegram. Default: queue on desk + web push.
    Graph publish only when desk_only=False (legacy; not used in prod).
    """
    if not cfg.enabled:
        return {"posted": False, "reason": "news_pulse_disabled"}

    if not tier_meets_minimum(tier, cfg.min_tier):
        return {"posted": False, "reason": f"tier_{tier}_below_{cfg.min_tier}"}

    article_hash = article.get("hash", "")
    if cfg.skip_if_short_used and article_hash:
        try:
            from src.desk.catalog import used_short_hashes

            if article_hash in used_short_hashes():
                return {"posted": False, "reason": "short_already_used"}
        except Exception:
            pass

    state = load_threads_state(state_path, cfg.timezone)

    if article_hash and article_hash in state.posted_hashes:
        return {"posted": False, "reason": "already_posted_hash"}

    if state.post_count >= cfg.max_per_day:
        return {"posted": False, "reason": "daily_max_reached"}

    elapsed = _minutes_since_last(state, cfg.timezone)
    if elapsed is not None and elapsed < cfg.cooldown_minutes:
        return {"posted": False, "reason": "cooldown"}

    text, variant = build_threads_news_pulse(
        article,
        tier=tier,
        seed=article_hash,
        question_rate=cfg.question_rate,
    )
    if not (text or "").strip():
        return {"posted": False, "reason": "no_copy"}

    if dry_run:
        return {
            "posted": False,
            "dry_run": True,
            "desk": cfg.desk_only,
            "variant": variant,
            "text": text,
            "tier": tier,
        }

    if cfg.desk_only:
        from src.content.editorial_jobs import _push_desk_item

        queued = _push_desk_item("news", "Threads — новина", text)
        if not queued:
            return {
                "posted": False,
                "reason": "desk_push_failed",
                "desk_queued": False,
                "variant": variant,
                "text": text,
                "tier": tier,
            }
        state.post_count += 1
        state.last_post_at = datetime.now(ZoneInfo(cfg.timezone)).isoformat()
        if article_hash:
            state.posted_hashes.append(article_hash)
        save_threads_state(state_path, state)
        return {
            "posted": False,
            "desk_queued": True,
            "variant": variant,
            "text": text,
            "tier": tier,
            "post_count": state.post_count,
        }

    # Legacy Graph path (opt-in only).
    from src.publishers.threads_publisher import ThreadsPublisher

    publisher = ThreadsPublisher()
    if not publisher.configured():
        return {"posted": False, "reason": "threads_not_configured"}
    try:
        result = publisher.publish_text(text)
    except Exception as exc:
        log.exception("Threads news pulse failed")
        # Still land on desk so the operator is not blocked — only claim success if it worked.
        desk_queued = False
        try:
            from src.content.editorial_jobs import _push_desk_item

            desk_queued = bool(_push_desk_item("news", "Threads — новина", text))
        except Exception:
            log.exception("Threads desk fallback also failed")
        if desk_queued:
            state.post_count += 1
            state.last_post_at = datetime.now(ZoneInfo(cfg.timezone)).isoformat()
            if article_hash:
                state.posted_hashes.append(article_hash)
            save_threads_state(state_path, state)
        return {
            "posted": False,
            "reason": "publish_failed",
            "error": str(exc),
            "desk_queued": desk_queued,
            "text": text,
            "variant": variant,
        }

    state.post_count += 1
    state.last_post_at = datetime.now(ZoneInfo(cfg.timezone)).isoformat()
    if article_hash:
        state.posted_hashes.append(article_hash)
    save_threads_state(state_path, state)

    return {
        "posted": True,
        "variant": variant,
        "url": result.get("url"),
        "tier": tier,
        "post_count": state.post_count,
    }
