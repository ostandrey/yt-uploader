"""
Fetch high-resolution stock photos from Pexels/Pixabay for Shorts B-roll.
Photos are sharper than compressed stock video clips.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import requests

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PIXABAY_PHOTO_URL = "https://pixabay.com/api/"


class StockImageFetcher:
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

    def fetch_image_for_keyword(self, keyword: str) -> Optional[Dict]:
        candidates: List[Dict] = []
        if self.pexels_api_key and self.pexels_api_key != "your_pexels_api_key_here":
            candidates.extend(self._fetch_pexels(keyword))
        if self.pixabay_api_key and self.pixabay_api_key != "your_pixabay_api_key_here":
            candidates.extend(self._fetch_pixabay(keyword))

        for image in candidates:
            if image["url"] not in self.used_urls:
                self.used_urls.add(image["url"])
                return image

        if candidates:
            image = candidates[0]
            self.used_urls.add(image["url"])
            return image
        return None

    def _fetch_pexels(self, keyword: str) -> List[Dict]:
        results: List[Dict] = []
        try:
            response = requests.get(
                PEXELS_PHOTO_URL,
                headers={"Authorization": self.pexels_api_key},
                params={
                    "query": keyword,
                    "per_page": 15,
                    "orientation": "portrait",
                },
                timeout=15,
            )
            response.raise_for_status()
            for photo in response.json().get("photos", []):
                src = photo.get("src", {})
                url = src.get("original") or src.get("large2x") or src.get("large")
                if not url:
                    continue
                results.append({
                    "url": url,
                    "source": "pexels",
                    "keyword": keyword,
                    "width": photo.get("width", 0),
                    "height": photo.get("height", 0),
                })
        except requests.RequestException:
            pass
        return results

    def _fetch_pixabay(self, keyword: str) -> List[Dict]:
        results: List[Dict] = []
        try:
            response = requests.get(
                PIXABAY_PHOTO_URL,
                params={
                    "key": self.pixabay_api_key,
                    "q": keyword,
                    "image_type": "photo",
                    "orientation": "vertical",
                    "per_page": 15,
                },
                timeout=15,
            )
            response.raise_for_status()
            for hit in response.json().get("hits", []):
                url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not url:
                    continue
                results.append({
                    "url": url,
                    "source": "pixabay",
                    "keyword": keyword,
                    "width": hit.get("imageWidth", 0),
                    "height": hit.get("imageHeight", 0),
                })
        except requests.RequestException:
            pass
        return results

    def download_image(self, image: Dict, target: Path) -> Optional[Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.pexels.com/",
        }
        try:
            response = requests.get(image["url"], headers=headers, timeout=60, stream=True)
            response.raise_for_status()
            with open(target, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
            if target.stat().st_size > 5_000:
                return target
        except requests.RequestException:
            pass
        return None
