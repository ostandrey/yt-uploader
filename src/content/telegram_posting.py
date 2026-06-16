"""
Smart Telegram posting — 3–8 posts/day based on news strength.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from src.content.crypto_feeds import CryptoNewsFetcher
from src.content.market_ticker import fetch_market_ticker_line
from src.content.news_filter import (
    classify_telegram_tier,
    format_telegram_post_html,
    passes_telegram_filter,
)
from src.publishers.telegram_publisher import TelegramPublisher

STATE_FILE = Path("data/storage/coin_wire/telegram_daily_state.json")


@dataclass
class TelegramPostingConfig:
    min_posts_per_day: int = 3
    max_posts_per_day: int = 8
    breaking_score: int = 22
    strong_score: int = 15
    insight_score: int = 18
    min_score: int = 6
    max_age_hours: int = 48
    post_cooldown_minutes: int = 90
    floor_times: Tuple[Tuple[int, int], ...] = ((8, 0), (12, 0), (17, 0))
    timezone: str = "America/New_York"

    @classmethod
    def from_config(cls, config: dict) -> "TelegramPostingConfig":
        tg = config.get("publishing", {}).get("telegram", {})
        filters = config.get("content", {}).get("filters", {})
        automation = config.get("automation", {})
        floor_raw = automation.get("schedule", {}).get(
            "telegram_floor", ["08:00", "12:00", "17:00"]
        )
        floor_times: List[Tuple[int, int]] = []
        for item in floor_raw:
            hour, minute = item.strip().split(":")
            floor_times.append((int(hour), int(minute)))

        return cls(
            min_posts_per_day=int(tg.get("min_posts_per_day", 3)),
            max_posts_per_day=int(tg.get("max_posts_per_day", 8)),
            breaking_score=int(tg.get("breaking_score", 22)),
            strong_score=int(tg.get("strong_score", 15)),
            insight_score=int(tg.get("insight_score", 18)),
            min_score=int(filters.get("telegram_min_score", 6)),
            max_age_hours=int(filters.get("telegram_max_age_hours", 48)),
            post_cooldown_minutes=int(tg.get("post_cooldown_minutes", 90)),
            floor_times=tuple(floor_times) if floor_times else ((8, 0), (12, 0), (17, 0)),
            timezone=automation.get("timezone", "America/New_York"),
        )


@dataclass
class DailyState:
    date: str
    post_count: int = 0
    last_post_at: Optional[str] = None

    @classmethod
    def for_today(cls, tz_name: str) -> "DailyState":
        today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
        return cls(date=today, post_count=0)

    def minutes_since_last_post(self, tz_name: str) -> Optional[float]:
        if not self.last_post_at:
            return None
        last = datetime.fromisoformat(self.last_post_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=ZoneInfo(tz_name))
        now = datetime.now(ZoneInfo(tz_name))
        return (now - last).total_seconds() / 60


def load_daily_state(path: Path, tz_name: str) -> DailyState:
    today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    if not path.exists():
        return DailyState.for_today(tz_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("date") != today:
            return DailyState.for_today(tz_name)
        return DailyState(
            date=today,
            post_count=int(data.get("post_count", 0)),
            last_post_at=data.get("last_post_at"),
        )
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return DailyState.for_today(tz_name)


def save_daily_state(path: Path, state: DailyState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "date": state.date,
                "post_count": state.post_count,
                "last_post_at": state.last_post_at,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def expected_min_posts(now: datetime, floor_times: Tuple[Tuple[int, int], ...]) -> int:
    """How many posts we should have published by this time today."""
    minute_of_day = now.hour * 60 + now.minute
    needed = 0
    for hour, minute in floor_times:
        if minute_of_day >= hour * 60 + minute:
            needed += 1
    return needed


def decide_post(
    article: Dict,
    state: DailyState,
    cfg: TelegramPostingConfig,
    *,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    score = int(article.get("score", 0))
    tier = classify_telegram_tier(
        score,
        breaking_score=cfg.breaking_score,
        insight_score=cfg.insight_score,
        strong_score=cfg.strong_score,
        min_score=cfg.min_score,
    )

    if tier == "skip":
        return False, "below_min_score"

    if state.post_count >= cfg.max_posts_per_day:
        return False, "daily_max_reached"

    if tier == "breaking":
        return True, "breaking_news"

    now = now or datetime.now(ZoneInfo(cfg.timezone))
    floor_needed = expected_min_posts(now, cfg.floor_times)
    if state.post_count < min(floor_needed, cfg.min_posts_per_day):
        return True, "daily_floor"

    if tier in ("strong", "insight", "breaking"):
        elapsed = state.minutes_since_last_post(cfg.timezone)
        if elapsed is None or elapsed >= cfg.post_cooldown_minutes:
            return True, f"{tier}_with_cooldown"

    if now.hour >= 20 and state.post_count < cfg.min_posts_per_day:
        return True, "end_of_day_catchup"

    return False, "waiting_for_stronger_or_cooldown"


def run_smart_post(
    fetcher: CryptoNewsFetcher,
    publisher: TelegramPublisher,
    cfg: TelegramPostingConfig,
    *,
    state_path: Path = STATE_FILE,
    dry_run: bool = False,
) -> dict:
    state = load_daily_state(state_path, cfg.timezone)
    articles = fetcher.fetch_latest(count=5, skip_posted=True, for_short=False)

    if not articles:
        return {"posted": False, "reason": "no_candidates", "post_count": state.post_count}

    for article in articles:
        if not passes_telegram_filter(article, cfg.min_score, cfg.max_age_hours):
            continue

        should, reason = decide_post(article, state, cfg)
        if not should:
            continue

        score = int(article.get("score", 0))
        tier = classify_telegram_tier(
            score,
            breaking_score=cfg.breaking_score,
            insight_score=cfg.insight_score,
            strong_score=cfg.strong_score,
            min_score=cfg.min_score,
        )
        include_insight = score >= cfg.insight_score or tier == "breaking"
        market_line = fetch_market_ticker_line()
        text = format_telegram_post_html(
            article,
            tier=tier,
            market_line=market_line,
            include_insight=include_insight,
        )
        buttons = [{"text": "Read full story →", "url": article["link"]}]

        if dry_run:
            return {
                "posted": False,
                "dry_run": True,
                "reason": reason,
                "tier": tier,
                "score": score,
                "title": article["title"],
                "text": text,
                "post_count": state.post_count,
            }

        publisher.post_to_channel_html(text, buttons=buttons)
        fetcher.mark_posted(article)

        state.post_count += 1
        state.last_post_at = datetime.now(ZoneInfo(cfg.timezone)).isoformat()
        save_daily_state(state_path, state)

        return {
            "posted": True,
            "reason": reason,
            "tier": tier,
            "score": score,
            "title": article["title"],
            "post_count": state.post_count,
        }

    return {
        "posted": False,
        "reason": "no_article_passed_rules",
        "post_count": state.post_count,
        "best_score": articles[0].get("score") if articles else None,
    }
