"""
YouTube upload for Coin Wire — OAuth, unlisted upload, publish approval.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
CATEGORY_NEWS = "25"  # News & Politics


class YouTubePublisher:
    def __init__(
        self,
        token_file: Optional[Path] = None,
        channel_label: str = "Coin Wire",
    ):
        load_dotenv()
        root = Path(__file__).resolve().parents[2]

        self.token_file = Path(token_file or "tokens/coin_wire_token.json")
        if not self.token_file.is_absolute():
            self.token_file = root / self.token_file

        self.channel_label = channel_label
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self._service = None

    def _load_credentials(self) -> Credentials:
        creds: Optional[Credentials] = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_token(creds)
            return creds

        flow = InstalledAppFlow.from_client_config(
            oauth_client_config_from_env(), SCOPES
        )
        creds = flow.run_local_server(port=0)
        self._save_token(creds)
        return creds

    def _save_token(self, creds: Credentials) -> None:
        self.token_file.write_text(creds.to_json(), encoding="utf-8")

    @property
    def service(self):
        if self._service is None:
            creds = self._load_credentials()
            self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def get_channel_info(self) -> dict:
        response = self.service.channels().list(
            part="snippet,statistics", mine=True
        ).execute()
        items = response.get("items", [])
        if not items:
            raise RuntimeError("No YouTube channel found for this Google account.")
        channel = items[0]
        return {
            "id": channel["id"],
            "title": channel["snippet"]["title"],
            "subscribers": channel["statistics"].get("subscriberCount", "0"),
        }

    def upload_short(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "unlisted",
    ) -> str:
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or [])[:30],
                "categoryId": CATEGORY_NEWS,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            chunksize=1024 * 1024,
            resumable=True,
            mimetype="video/mp4",
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"      Upload: {int(status.progress() * 100)}%")

        video_id = response["id"]
        return video_id

    def set_thumbnail(self, video_id: str, image_path: Path) -> bool:
        """Upload custom JPEG thumbnail. Requires channel phone/ID verification."""
        if not image_path.exists():
            raise FileNotFoundError(f"Thumbnail not found: {image_path}")

        media = MediaFileUpload(str(image_path), mimetype="image/jpeg", resumable=True)
        try:
            self.service.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            return True
        except HttpError as exc:
            print(f"      Thumbnail upload skipped: {exc}")
            return False

    def set_privacy(self, video_id: str, privacy_status: str) -> None:
        response = self.service.videos().list(part="status", id=video_id).execute()
        items = response.get("items", [])
        if not items:
            raise RuntimeError(f"Video not found: {video_id}")

        item = items[0]
        item["status"]["privacyStatus"] = privacy_status
        self.service.videos().update(part="status", body=item).execute()

    @staticmethod
    def short_url(video_id: str) -> str:
        return f"https://youtube.com/shorts/{video_id}"

    @staticmethod
    def studio_url(video_id: str) -> str:
        return f"https://studio.youtube.com/video/{video_id}/edit"


def oauth_client_config_from_env() -> dict:
    """OAuth client config from YOUTUBE_CRYPTO_CLIENT_ID/SECRET in .env."""
    load_dotenv()
    client_id = os.getenv("YOUTUBE_CRYPTO_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CRYPTO_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise ValueError(
            "Set YOUTUBE_CRYPTO_CLIENT_ID and YOUTUBE_CRYPTO_CLIENT_SECRET in .env"
        )

    return {
        "installed": {
            "client_id": client_id,
            "project_id": "coin-wire-uploader",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
        }
    }
