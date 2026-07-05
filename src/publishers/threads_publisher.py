"""
Threads video posts via Threads Graph API.

Env:
  THREADS_ACCESS_TOKEN  (or META_ACCESS_TOKEN / THREADS token)
  THREADS_USER_ID
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

GRAPH = "https://graph.threads.net/v1.0"


class ThreadsPublisher:
    def __init__(
        self,
        access_token: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        load_dotenv()
        self.access_token = (
            access_token
            or os.getenv("THREADS_ACCESS_TOKEN")
            or os.getenv("META_ACCESS_TOKEN")
            or ""
        ).strip()
        self.user_id = (user_id or os.getenv("THREADS_USER_ID") or "").strip()

    def configured(self) -> bool:
        return bool(self.access_token and self.user_id)

    def publish_video(
        self,
        video_url: str,
        text: str,
        *,
        max_wait_sec: int = 300,
    ) -> dict:
        if not self.configured():
            raise RuntimeError(
                "Threads not configured (THREADS_ACCESS_TOKEN + THREADS_USER_ID)"
            )

        create = requests.post(
            f"{GRAPH}/{self.user_id}/threads",
            data={
                "media_type": "VIDEO",
                "video_url": video_url,
                "text": text[:500],
                "access_token": self.access_token,
            },
            timeout=60,
        )
        create_data = create.json()
        creation_id = create_data.get("id")
        if not creation_id:
            raise RuntimeError(f"Threads container failed: {create_data}")

        self._wait_container(creation_id, max_wait_sec=max_wait_sec)

        publish = requests.post(
            f"{GRAPH}/{self.user_id}/threads_publish",
            data={
                "creation_id": creation_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        publish_data = publish.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise RuntimeError(f"Threads publish failed: {publish_data}")

        return {
            "platform": "threads",
            "post_id": post_id,
            "creation_id": creation_id,
            "url": f"https://www.threads.net/post/{post_id}",
        }

    def publish_text(self, text: str) -> dict:
        """Text-only fallback when video host is unavailable."""
        if not self.configured():
            raise RuntimeError(
                "Threads not configured (THREADS_ACCESS_TOKEN + THREADS_USER_ID)"
            )

        create = requests.post(
            f"{GRAPH}/{self.user_id}/threads",
            data={
                "media_type": "TEXT",
                "text": text[:500],
                "access_token": self.access_token,
            },
            timeout=60,
        )
        create_data = create.json()
        creation_id = create_data.get("id")
        if not creation_id:
            raise RuntimeError(f"Threads text container failed: {create_data}")

        publish = requests.post(
            f"{GRAPH}/{self.user_id}/threads_publish",
            data={
                "creation_id": creation_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        publish_data = publish.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise RuntimeError(f"Threads text publish failed: {publish_data}")

        return {
            "platform": "threads",
            "post_id": post_id,
            "mode": "text",
            "url": f"https://www.threads.net/post/{post_id}",
        }

    def _wait_container(self, creation_id: str, *, max_wait_sec: int) -> None:
        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            response = requests.get(
                f"{GRAPH}/{creation_id}",
                params={
                    "fields": "status,error_message",
                    "access_token": self.access_token,
                },
                timeout=30,
            )
            data = response.json()
            status = (data.get("status") or "").upper()
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Threads processing failed: {data}")
            # Some responses omit status until ready
            if data.get("id") and not data.get("error"):
                # still processing
                pass
            time.sleep(5)
        raise RuntimeError(f"Threads processing timeout for {creation_id}")
