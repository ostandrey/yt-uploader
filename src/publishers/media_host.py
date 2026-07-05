"""
Temporary public hosting for Meta APIs (Instagram needs public media URLs).

Uses S3-compatible storage (AWS S3, Cloudflare R2, MinIO).
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def media_host_configured() -> bool:
    return bool(
        os.getenv("CROSSPOST_S3_BUCKET")
        and os.getenv("CROSSPOST_S3_ACCESS_KEY")
        and os.getenv("CROSSPOST_S3_SECRET_KEY")
        and os.getenv("CROSSPOST_S3_PUBLIC_BASE_URL")
    )


_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _content_type(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def upload_public_file(file_path: Path, *, prefix: str = "coinwire") -> str:
    """
    Upload a media file and return a publicly reachable HTTPS URL.
    Raises RuntimeError if host is not configured or upload fails.
    """
    if not media_host_configured():
        raise RuntimeError(
            "Media host not configured. Set CROSSPOST_S3_BUCKET, "
            "CROSSPOST_S3_ACCESS_KEY, CROSSPOST_S3_SECRET_KEY, "
            "CROSSPOST_S3_PUBLIC_BASE_URL (S3 or Cloudflare R2)."
        )

    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:
        raise RuntimeError("boto3 is required for Instagram uploads") from exc

    file_path = Path(file_path)
    bucket = os.environ["CROSSPOST_S3_BUCKET"]
    access_key = os.environ["CROSSPOST_S3_ACCESS_KEY"]
    secret_key = os.environ["CROSSPOST_S3_SECRET_KEY"]
    public_base = os.environ["CROSSPOST_S3_PUBLIC_BASE_URL"].rstrip("/")
    endpoint = os.getenv("CROSSPOST_S3_ENDPOINT") or None
    region = os.getenv("CROSSPOST_S3_REGION", "auto")

    ext = file_path.suffix.lower() or ".bin"
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"
    client_kwargs = {
        "service_name": "s3",
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "region_name": region,
        "config": Config(signature_version="s3v4"),
    }
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint

    client = boto3.client(**client_kwargs)
    extra = {"ContentType": _content_type(file_path)}
    acl = os.getenv("CROSSPOST_S3_ACL", "").strip()
    if acl:
        extra["ACL"] = acl

    client.upload_file(
        str(file_path),
        bucket,
        key,
        ExtraArgs=extra,
    )
    url = f"{public_base}/{key}"
    log.info("Uploaded public media: %s", url)
    return url


def upload_public_video(video_path: Path, *, prefix: str = "coinwire") -> str:
    """Upload MP4 and return a publicly reachable HTTPS URL."""
    return upload_public_file(video_path, prefix=prefix)
