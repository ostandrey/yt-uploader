"""
Fetch stock videos from Pexels and Pixabay for Shorts backgrounds.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional

import requests


PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"


# Free Pexels CDN clips used when no API key is configured (demo/fallback).
FALLBACK_VIDEO_URLS = [
    "https://videos.pexels.com/video-files/6774633/6774633-uhd_1440_2732_25fps.mp4",
    "https://videos.pexels.com/video-files/3945311/3945311-uhd_2160_4096_25fps.mp4",
    "https://videos.pexels.com/video-files/3129671/3129671-uhd_2160_4096_24fps.mp4",
    "https://videos.pexels.com/video-files/7579579/7579579-uhd_1440_2732_25fps.mp4",
]


class StockVideoFetcher:
    def __init__(
        self,
        pexels_api_key: Optional[str] = None,
        pixabay_api_key: Optional[str] = None,
    ):
        self.pexels_api_key = pexels_api_key or os.getenv("PEXELS_API_KEY")
        self.pixabay_api_key = pixabay_api_key or os.getenv("PIXABAY_API_KEY")
        self.used_urls: set[str] = set()

    def reset_used(self) -> None:
        self.used_urls.clear()

    def fetch_videos(
        self,
        keywords: List[str],
        count: int = 4,
        orientation: str = "portrait",
    ) -> List[Dict]:
        videos: List[Dict] = []

        if self.pexels_api_key and self.pexels_api_key != "your_pexels_api_key_here":
            videos.extend(self._fetch_pexels(keywords, count, orientation))

        if len(videos) < count and self.pixabay_api_key and self.pixabay_api_key != "your_pixabay_api_key_here":
            videos.extend(self._fetch_pixabay(keywords, count - len(videos)))

        if len(videos) < count:
            videos.extend(self._fallback_videos(count - len(videos)))

        return videos[:count]

    def _video_from_pexels_item(self, item: Dict, keyword: str) -> Optional[Dict]:
        if item.get("duration", 0) < 4:
            return None
        files = item.get("video_files", [])
        vertical = [
            f for f in files
            if f.get("height", 0) >= f.get("width", 0)
        ]
        hd_vertical = [f for f in vertical if f.get("height", 0) >= 1080]
        pool = hd_vertical or vertical
        if not pool:
            pool = files
        chosen = max(
            pool,
            key=lambda f: f.get("width", 0) * f.get("height", 0),
        )
        if not chosen:
            return None
        return {
            "url": chosen["link"],
            "source": "pexels",
            "keyword": keyword,
            "type": "video",
            "duration": item.get("duration", 0),
            "width": chosen.get("width", 0),
            "height": chosen.get("height", 0),
        }

    def _fetch_pexels_keyword(
        self,
        keyword: str,
        count: int,
        orientation: str,
    ) -> List[Dict]:
        if not self.pexels_api_key or self.pexels_api_key == "your_pexels_api_key_here":
            return []

        results: List[Dict] = []
        headers = {"Authorization": self.pexels_api_key}
        try:
            response = requests.get(
                PEXELS_VIDEO_URL,
                headers=headers,
                params={
                    "query": keyword,
                    "per_page": max(count, 15),
                    "orientation": orientation,
                    "size": "large",
                },
                timeout=15,
            )
            response.raise_for_status()
            for item in response.json().get("videos", []):
                video = self._video_from_pexels_item(item, keyword)
                if video:
                    results.append(video)
        except requests.RequestException:
            pass
        return results

    def _fetch_pexels(
        self, keywords: List[str], count: int, orientation: str
    ) -> List[Dict]:
        results: List[Dict] = []
        for keyword in keywords:
            if len(results) >= count:
                break
            for video in self._fetch_pexels_keyword(keyword, count, orientation):
                if video["url"] not in {r["url"] for r in results}:
                    results.append(video)
                if len(results) >= count:
                    break
        return results

    def _fetch_pixabay(self, keywords: List[str], count: int) -> List[Dict]:
        results: List[Dict] = []

        for keyword in keywords:
            if len(results) >= count:
                break
            try:
                response = requests.get(
                    PIXABAY_VIDEO_URL,
                    params={
                        "key": self.pixabay_api_key,
                        "q": keyword,
                        "per_page": min(count, 10),
                        "video_type": "film",
                    },
                    timeout=15,
                )
                response.raise_for_status()
                for hit in response.json().get("hits", []):
                    if len(results) >= count:
                        break
                    videos = hit.get("videos", {})
                    chosen = (
                        videos.get("large")
                        or videos.get("medium")
                        or videos.get("small")
                    )
                    if chosen and chosen.get("url"):
                        results.append({
                            "url": chosen["url"],
                            "source": "pixabay",
                            "keyword": keyword,
                            "type": "video",
                            "width": chosen.get("width", 0),
                            "height": chosen.get("height", 0),
                        })
            except requests.RequestException:
                continue

        return results

    def _fallback_videos(self, count: int) -> List[Dict]:
        urls = random.sample(
            FALLBACK_VIDEO_URLS,
            k=min(count, len(FALLBACK_VIDEO_URLS)),
        )
        return [
            {"url": url, "source": "fallback", "keyword": "finance", "type": "video"}
            for url in urls
        ]

    def fetch_video_for_keyword(
        self,
        keyword: str,
        orientation: str = "portrait",
        min_height: int = 1080,
    ) -> Optional[Dict]:
        candidates: List[Dict] = []
        if self.pexels_api_key and self.pexels_api_key != "your_pexels_api_key_here":
            candidates.extend(self._fetch_pexels_keyword(keyword, 20, orientation))

        if len(candidates) < 3 and self.pixabay_api_key and self.pixabay_api_key != "your_pixabay_api_key_here":
            candidates.extend(self._fetch_pixabay([keyword], 15))

        if len(candidates) < 1:
            candidates.extend(self._fallback_videos(4))

        candidates.sort(
            key=lambda v: v.get("width", 0) * v.get("height", 0),
            reverse=True,
        )

        for video in candidates:
            if video.get("height", 0) < min_height:
                continue
            if video["url"] not in self.used_urls:
                self.used_urls.add(video["url"])
                return video

        for video in candidates:
            if video["url"] not in self.used_urls:
                self.used_urls.add(video["url"])
                return video

        video = candidates[0] if candidates else None
        if video:
            self.used_urls.add(video["url"])
        return video

    def download_video(self, video: Dict, target: Path, use_cache: bool = False) -> Optional[Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if use_cache and target.exists() and target.stat().st_size > 10_000:
            return target

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.pexels.com/",
            "Accept": "*/*",
        }
        try:
            response = requests.get(
                video["url"],
                headers=headers,
                timeout=90,
                stream=True,
            )
            response.raise_for_status()
            with open(target, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
            if target.stat().st_size > 10_000:
                return target
        except requests.RequestException:
            pass
        return None

    def download_videos(self, videos: List[Dict], output_dir: Path) -> List[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.pexels.com/",
            "Accept": "*/*",
        }

        for index, video in enumerate(videos):
            target = output_dir / f"clip_{index:02d}.mp4"
            if target.exists() and target.stat().st_size > 10_000:
                paths.append(target)
                continue
            try:
                response = requests.get(
                    video["url"],
                    headers=headers,
                    timeout=90,
                    stream=True,
                )
                response.raise_for_status()
                with open(target, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)
                if target.stat().st_size > 10_000:
                    paths.append(target)
            except requests.RequestException:
                continue

        return paths
