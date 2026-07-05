"""
TikTok Content Posting API — direct video upload (no public URL needed).

Env:
  TIKTOK_CLIENT_KEY
  TIKTOK_CLIENT_SECRET
  TIKTOK_ACCESS_TOKEN
  TIKTOK_REFRESH_TOKEN   (optional, enables auto-refresh)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
REFRESH_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TOKEN_FILE = Path("tokens/tiktok_token.json")


class TikTokPublisher:
    def __init__(
        self,
        access_token: Optional[str] = None,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
    ):
        load_dotenv()
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
        self.privacy_level = privacy_level
        self.access_token = access_token or self._load_access_token()

    def configured(self) -> bool:
        return bool(self.access_token)

    def _token_path(self) -> Path:
        root = Path(__file__).resolve().parents[2]
        path = TOKEN_FILE
        if not path.is_absolute():
            path = root / path
        return path

    def _load_access_token(self) -> str:
        env_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
        path = self._token_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return (data.get("access_token") or env_token).strip()
            except (OSError, json.JSONDecodeError):
                pass
        return env_token

    def _save_tokens(self, access_token: str, refresh_token: str = "") -> None:
        path = self._token_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": access_token,
            "refresh_token": refresh_token
            or os.getenv("TIKTOK_REFRESH_TOKEN", ""),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.access_token = access_token

    def refresh_access_token(self) -> bool:
        refresh = os.getenv("TIKTOK_REFRESH_TOKEN", "").strip()
        path = self._token_path()
        if path.exists():
            try:
                refresh = json.loads(path.read_text(encoding="utf-8")).get(
                    "refresh_token", refresh
                )
            except (OSError, json.JSONDecodeError):
                pass
        if not refresh or not self.client_key or not self.client_secret:
            return False

        response = requests.post(
            REFRESH_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            timeout=30,
        )
        data = response.json()
        token = data.get("access_token") or data.get("data", {}).get("access_token")
        new_refresh = (
            data.get("refresh_token")
            or data.get("data", {}).get("refresh_token")
            or refresh
        )
        if not token:
            log.warning("TikTok token refresh failed: %s", data)
            return False
        self._save_tokens(token, new_refresh)
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def upload_video(
        self,
        video_path: Path,
        caption: str,
        *,
        max_wait_sec: int = 180,
    ) -> dict:
        if not self.configured():
            raise RuntimeError("TikTok not configured (TIKTOK_ACCESS_TOKEN)")
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        size = video_path.stat().st_size
        init_body = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": self.privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }

        response = requests.post(
            INIT_URL, headers=self._headers(), json=init_body, timeout=60
        )
        if response.status_code == 401 and self.refresh_access_token():
            response = requests.post(
                INIT_URL, headers=self._headers(), json=init_body, timeout=60
            )

        payload = response.json()
        data = payload.get("data") or {}
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url or not publish_id:
            error = payload.get("error") or payload
            raise RuntimeError(f"TikTok init failed: {error}")

        with open(video_path, "rb") as handle:
            video_bytes = handle.read()

        put = requests.put(
            upload_url,
            data=video_bytes,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            timeout=300,
        )
        if put.status_code not in (200, 201):
            raise RuntimeError(
                f"TikTok upload failed ({put.status_code}): {put.text[:300]}"
            )

        status = self._wait_publish(publish_id, max_wait_sec=max_wait_sec)
        return {
            "platform": "tiktok",
            "publish_id": publish_id,
            "status": status.get("status", "unknown"),
            "raw": status,
        }

    def _wait_publish(self, publish_id: str, *, max_wait_sec: int) -> dict:
        deadline = time.time() + max_wait_sec
        last: dict = {}
        while time.time() < deadline:
            response = requests.post(
                STATUS_URL,
                headers=self._headers(),
                json={"publish_id": publish_id},
                timeout=30,
            )
            last = (response.json().get("data") or {})
            status = (last.get("status") or "").upper()
            if status in ("PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"):
                if status == "FAILED":
                    raise RuntimeError(f"TikTok publish failed: {last}")
                return last
            time.sleep(5)
        return last or {"status": "TIMEOUT", "publish_id": publish_id}
