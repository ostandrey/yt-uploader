"""
Instagram Reels via Meta Graph API.

Requires:
  - Instagram Business/Creator account linked to a Facebook Page
  - Long-lived Page access token with instagram_content_publish
  - Public video URL (see media_host.py)

Env:
  META_ACCESS_TOKEN   (or INSTAGRAM_ACCESS_TOKEN)
  INSTAGRAM_USER_ID   (IG user id, not page id)
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramPublisher:
    def __init__(
        self,
        access_token: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        load_dotenv()
        self.access_token = (
            access_token
            or os.getenv("INSTAGRAM_ACCESS_TOKEN")
            or os.getenv("META_ACCESS_TOKEN")
            or ""
        ).strip()
        self.user_id = (user_id or os.getenv("INSTAGRAM_USER_ID") or "").strip()

    def configured(self) -> bool:
        return bool(self.access_token and self.user_id)

    def publish_reel(
        self,
        video_url: str,
        caption: str,
        *,
        share_to_feed: bool = True,
        max_wait_sec: int = 300,
    ) -> dict:
        if not self.configured():
            raise RuntimeError(
                "Instagram not configured (META_ACCESS_TOKEN + INSTAGRAM_USER_ID)"
            )

        create = requests.post(
            f"{GRAPH}/{self.user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "share_to_feed": "true" if share_to_feed else "false",
                "access_token": self.access_token,
            },
            timeout=60,
        )
        create_data = create.json()
        creation_id = create_data.get("id")
        if not creation_id:
            raise RuntimeError(f"Instagram container failed: {create_data}")

        self._wait_container(creation_id, max_wait_sec=max_wait_sec)

        media_id = self._publish_container(creation_id)
        return {
            "platform": "instagram",
            "format": "reel",
            "media_id": media_id,
            "creation_id": creation_id,
            "url": f"https://www.instagram.com/reel/{media_id}/",
        }

    def publish_image(
        self,
        image_url: str,
        caption: str,
        *,
        max_wait_sec: int = 300,
    ) -> dict:
        if not self.configured():
            raise RuntimeError(
                "Instagram not configured (META_ACCESS_TOKEN + INSTAGRAM_USER_ID)"
            )

        create = requests.post(
            f"{GRAPH}/{self.user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption[:2200],
                "access_token": self.access_token,
            },
            timeout=60,
        )
        create_data = create.json()
        creation_id = create_data.get("id")
        if not creation_id:
            raise RuntimeError(f"Instagram image container failed: {create_data}")

        self._wait_container(creation_id, max_wait_sec=max_wait_sec)
        media_id = self._publish_container(creation_id)
        return {
            "platform": "instagram",
            "format": "feed",
            "media_id": media_id,
            "creation_id": creation_id,
            "url": f"https://www.instagram.com/p/{media_id}/",
        }

    def publish_carousel(
        self,
        image_urls: List[str],
        caption: str,
        *,
        max_wait_sec: int = 300,
    ) -> dict:
        if not self.configured():
            raise RuntimeError(
                "Instagram not configured (META_ACCESS_TOKEN + INSTAGRAM_USER_ID)"
            )
        if len(image_urls) < 2:
            raise ValueError("Instagram carousel requires at least 2 images")

        child_ids: list[str] = []
        for image_url in image_urls[:10]:
            create = requests.post(
                f"{GRAPH}/{self.user_id}/media",
                data={
                    "image_url": image_url,
                    "is_carousel_item": "true",
                    "access_token": self.access_token,
                },
                timeout=60,
            )
            create_data = create.json()
            child_id = create_data.get("id")
            if not child_id:
                raise RuntimeError(f"Instagram carousel item failed: {create_data}")
            child_ids.append(child_id)

        create = requests.post(
            f"{GRAPH}/{self.user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption[:2200],
                "access_token": self.access_token,
            },
            timeout=60,
        )
        create_data = create.json()
        creation_id = create_data.get("id")
        if not creation_id:
            raise RuntimeError(f"Instagram carousel container failed: {create_data}")

        self._wait_container(creation_id, max_wait_sec=max_wait_sec)
        media_id = self._publish_container(creation_id)
        return {
            "platform": "instagram",
            "format": "carousel",
            "media_id": media_id,
            "creation_id": creation_id,
            "url": f"https://www.instagram.com/p/{media_id}/",
        }

    def _publish_container(self, creation_id: str) -> str:
        publish = requests.post(
            f"{GRAPH}/{self.user_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        publish_data = publish.json()
        media_id = publish_data.get("id")
        if not media_id:
            raise RuntimeError(f"Instagram publish failed: {publish_data}")
        return media_id

    def _wait_container(self, creation_id: str, *, max_wait_sec: int) -> None:
        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            response = requests.get(
                f"{GRAPH}/{creation_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
                timeout=30,
            )
            data = response.json()
            status = (data.get("status_code") or "").upper()
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram processing failed: {data}")
            time.sleep(5)
        raise RuntimeError(f"Instagram processing timeout for {creation_id}")
