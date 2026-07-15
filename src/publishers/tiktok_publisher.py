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
INIT_INBOX_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
REFRESH_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TOKEN_FILE = Path("tokens/tiktok_token.json")

# TikTok FILE_UPLOAD chunk rules (see Content Posting media transfer guide)
_MIN_CHUNK = 5 * 1024 * 1024
_MAX_CHUNK = 64 * 1024 * 1024
_DEFAULT_CHUNK = 10 * 1024 * 1024


def _plan_chunks(video_size: int) -> tuple[int, int]:
    """Return (chunk_size, total_chunk_count) valid for TikTok FILE_UPLOAD."""
    if video_size <= 0:
        raise ValueError("video_size must be positive")
    if video_size < _MIN_CHUNK:
        return video_size, 1
    if video_size <= _MAX_CHUNK:
        return video_size, 1
    chunk_size = _DEFAULT_CHUNK
    total = video_size // chunk_size
    # Last chunk absorbs remainder; must stay >= 5MB and <= 128MB.
    remainder = video_size - (total - 1) * chunk_size if total > 0 else video_size
    if total < 1:
        total = 1
    if remainder > 128 * 1024 * 1024:
        # rarer huge-trail case: use larger base chunk
        chunk_size = _MAX_CHUNK
        total = video_size // chunk_size
    return chunk_size, total


class TikTokPublisher:
    def __init__(
        self,
        access_token: Optional[str] = None,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        *,
        draft: bool = False,
    ):
        load_dotenv()
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
        self.privacy_level = privacy_level
        # draft=True → inbox API (scope video.upload). Direct post needs video.publish.
        self.draft = draft
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
        chunk_size, total_chunks = _plan_chunks(size)
        source_info = {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        }
        if self.draft:
            init_url = INIT_INBOX_URL
            init_body = {"source_info": source_info}
        else:
            init_url = INIT_URL
            init_body = {
                "post_info": {
                    "title": caption[:2200],
                    "privacy_level": self.privacy_level,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": source_info,
            }

        response = requests.post(
            init_url, headers=self._headers(), json=init_body, timeout=60
        )
        if response.status_code == 401 and self.refresh_access_token():
            response = requests.post(
                init_url, headers=self._headers(), json=init_body, timeout=60
            )

        payload = response.json()
        data = payload.get("data") or {}
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url or not publish_id:
            error = payload.get("error") or payload
            raise RuntimeError(f"TikTok init failed: {error}")

        self._put_file_chunks(video_path, upload_url, size, chunk_size, total_chunks)

        status = self._wait_publish(publish_id, max_wait_sec=max_wait_sec)
        return {
            "platform": "tiktok",
            "publish_id": publish_id,
            "status": status.get("status", "unknown"),
            "draft": self.draft,
            "raw": status,
        }

    def _put_file_chunks(
        self,
        video_path: Path,
        upload_url: str,
        size: int,
        chunk_size: int,
        total_chunks: int,
    ) -> None:
        with open(video_path, "rb") as handle:
            for index in range(total_chunks):
                start = index * chunk_size
                if index == total_chunks - 1:
                    end = size
                else:
                    end = start + chunk_size
                handle.seek(start)
                chunk = handle.read(end - start)
                put = requests.put(
                    upload_url,
                    data=chunk,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end - 1}/{size}",
                    },
                    timeout=300,
                )
                # 206 = more chunks; 200/201 = done
                if put.status_code not in (200, 201, 206):
                    raise RuntimeError(
                        f"TikTok upload chunk {index + 1}/{total_chunks} "
                        f"failed ({put.status_code}): {put.text[:300]}"
                    )
                log.info(
                    "TikTok chunk %s/%s uploaded (%s bytes)",
                    index + 1,
                    total_chunks,
                    len(chunk),
                )

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
