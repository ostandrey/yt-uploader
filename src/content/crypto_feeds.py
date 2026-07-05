"""
Crypto news RSS fetcher for Coin Wire.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional

import feedparser

from src.content.naturalize import naturalize_text
from src.content.news_filter import (
    format_telegram_post,
    passes_short_filter,
    passes_telegram_filter,
    score_article,
)

CRYPTO_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "the_block": "https://www.theblock.co/rss.xml",
    "decrypt": "https://decrypt.co/feed",
}


def _clean_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _article_hash(title: str, link: str) -> str:
    raw = f"{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CryptoNewsFetcher:
    def __init__(
        self,
        feeds: Optional[Dict[str, str]] = None,
        posted_cache_path: Optional[Path] = None,
        short_min_score: int = 12,
        telegram_min_score: int = 6,
        short_max_age_hours: int = 24,
        telegram_max_age_hours: int = 48,
    ):
        self.feeds = feeds or CRYPTO_FEEDS
        self.posted_cache_path = posted_cache_path or Path(
            "data/storage/coin_wire/posted_articles.json"
        )
        self.short_min_score = short_min_score
        self.telegram_min_score = telegram_min_score
        self.short_max_age_hours = short_max_age_hours
        self.telegram_max_age_hours = telegram_max_age_hours
        self.posted_cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_posted(self) -> set[str]:
        if not self.posted_cache_path.exists():
            return set()
        try:
            data = json.loads(self.posted_cache_path.read_text(encoding="utf-8"))
            return set(data.get("hashes", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _save_posted(self, hashes: set[str]) -> None:
        trimmed = list(hashes)[-500:]
        payload = {"hashes": trimmed, "updated": datetime.utcnow().isoformat()}
        self.posted_cache_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def mark_posted(self, article: Dict) -> None:
        posted = self._load_posted()
        posted.add(article["hash"])
        self._save_posted(posted)

    def _fetch_feed(self, source: str, url: str, max_age_days: int = 3) -> List[Dict]:
        feed = feedparser.parse(url)
        articles: List[Dict] = []

        for entry in feed.entries[:15]:
            title = _clean_html(entry.get("title", ""))
            summary = _clean_html(entry.get("summary", ""))[:600]
            link = entry.get("link", "")
            if not title or not link:
                continue

            published = entry.get("published_parsed")
            if published:
                pub_date = datetime(*published[:6])
                if pub_date < datetime.now() - timedelta(days=max_age_days):
                    continue

            articles.append({
                "title": naturalize_text(title),
                "summary": naturalize_text(summary),
                "link": link,
                "source": source,
                "hash": _article_hash(title, link),
                "published": published,
                "score": 0,
            })

        return articles

    def _collect_all(self) -> List[Dict]:
        all_articles: List[Dict] = []
        for source, url in self.feeds.items():
            try:
                all_articles.extend(self._fetch_feed(source, url))
                time.sleep(0.3)
            except Exception:
                continue
        for article in all_articles:
            article["score"] = score_article(article, self.short_min_score)
        return all_articles

    def fetch_latest(
        self,
        count: int = 5,
        skip_posted: bool = True,
        for_short: bool = False,
    ) -> List[Dict]:
        posted = self._load_posted() if skip_posted else set()
        all_articles = self._collect_all()

        if for_short:
            fresh = [
                a for a in all_articles
                if a["hash"] not in posted
                and passes_short_filter(a, self.short_min_score, self.short_max_age_hours)
            ]
        else:
            fresh = [
                a for a in all_articles
                if a["hash"] not in posted
                and passes_telegram_filter(a, self.telegram_min_score, self.telegram_max_age_hours)
            ]

        fresh.sort(key=lambda a: a["score"], reverse=True)

        unique: List[Dict] = []
        seen: set[str] = set()
        for article in fresh:
            if article["hash"] in seen:
                continue
            seen.add(article["hash"])
            unique.append(article)
            if len(unique) >= count:
                break
        return unique

    def fetch_best_for_short(self, skip_hashes: Optional[set[str]] = None) -> Optional[Dict]:
        """Top serious article for a Short — auto-scored, no human review."""
        posted = self._load_posted()
        skip = skip_hashes or set()
        all_articles = self._collect_all()

        candidates = [
            a for a in all_articles
            if a["hash"] not in posted
            and a["hash"] not in skip
            and passes_short_filter(a, self.short_min_score, self.short_max_age_hours)
        ]
        candidates.sort(key=lambda a: a["score"], reverse=True)
        return candidates[0] if candidates else None

    def format_telegram_post(self, article: Dict) -> str:
        return format_telegram_post(article)

    @classmethod
    def from_config(cls, config: dict) -> "CryptoNewsFetcher":
        content = config.get("content", {})
        feeds = content.get("rss_feeds") or CRYPTO_FEEDS
        filters = content.get("filters", {})
        return cls(
            feeds=feeds,
            short_min_score=filters.get("short_min_score", 12),
            telegram_min_score=filters.get("telegram_min_score", 6),
            short_max_age_hours=filters.get("short_max_age_hours", 24),
            telegram_max_age_hours=filters.get("telegram_max_age_hours", 48),
        )

