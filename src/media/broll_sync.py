"""
Sync local B-roll library ↔ S3-compatible storage (Cloudflare R2).

Upload once from your PC, then Railway workers pull missing clips onto a
persistent volume at data/assets/broll_library/.

Uses the same credentials as Instagram media host by default:
  CROSSPOST_S3_BUCKET / ACCESS_KEY / SECRET_KEY / ENDPOINT / REGION

Optional overrides: BROLL_S3_* (same names).
Objects key prefix: broll_library/{category}/file.mp4 (+ *.meta.json)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from src.media.broll_library import DEFAULT_LIBRARY

log = logging.getLogger(__name__)

SKIP_DIR_NAMES = {"_rejected", "_qa_work", "_clip_work"}
SYNC_SUFFIXES = {".mp4", ".meta.json", ".json"}
DEFAULT_PREFIX = "broll_library"


@dataclass
class SyncConfig:
    library_root: Path
    bucket: str
    access_key: str
    secret_key: str
    endpoint: Optional[str]
    region: str
    prefix: str = DEFAULT_PREFIX

    @classmethod
    def from_env(cls, library_root: Optional[Path] = None) -> Optional["SyncConfig"]:
        def _get(*names: str) -> str:
            for name in names:
                value = os.getenv(name, "").strip()
                if value:
                    return value
            return ""

        bucket = _get("BROLL_S3_BUCKET", "CROSSPOST_S3_BUCKET")
        access = _get("BROLL_S3_ACCESS_KEY", "CROSSPOST_S3_ACCESS_KEY")
        secret = _get("BROLL_S3_SECRET_KEY", "CROSSPOST_S3_SECRET_KEY")
        if not (bucket and access and secret):
            return None
        return cls(
            library_root=Path(library_root or DEFAULT_LIBRARY),
            bucket=bucket,
            access_key=access,
            secret_key=secret,
            endpoint=_get("BROLL_S3_ENDPOINT", "CROSSPOST_S3_ENDPOINT") or None,
            region=_get("BROLL_S3_REGION", "CROSSPOST_S3_REGION") or "auto",
            prefix=_get("BROLL_S3_PREFIX") or DEFAULT_PREFIX,
        )


def sync_configured() -> bool:
    return SyncConfig.from_env() is not None


def _client(cfg: SyncConfig):
    import boto3
    from botocore.client import Config

    kwargs = {
        "service_name": "s3",
        "aws_access_key_id": cfg.access_key,
        "aws_secret_access_key": cfg.secret_key,
        "region_name": cfg.region,
        "config": Config(signature_version="s3v4"),
    }
    if cfg.endpoint:
        kwargs["endpoint_url"] = cfg.endpoint
    return boto3.client(**kwargs)


def _should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in SKIP_DIR_NAMES for part in rel_parts)


def _iter_local_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path, root):
            continue
        name = path.name
        if name.endswith(".meta.json") or path.suffix.lower() in {".mp4", ".json"}:
            yield path


def _key_for(cfg: SyncConfig, local: Path) -> str:
    rel = local.relative_to(cfg.library_root).as_posix()
    return f"{cfg.prefix.rstrip('/')}/{rel}"


def _list_remote_keys(cfg: SyncConfig) -> dict[str, int]:
    """Map object key → size."""
    client = _client(cfg)
    prefix = cfg.prefix.rstrip("/") + "/"
    keys: dict[str, int] = {}
    token: Optional[str] = None
    while True:
        kwargs = {"Bucket": cfg.bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for item in resp.get("Contents") or []:
            key = item["Key"]
            if any(f"/{skip}/" in f"/{key}/" for skip in SKIP_DIR_NAMES):
                continue
            keys[key] = int(item.get("Size") or 0)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def upload_library(
    *,
    library_root: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    cfg = SyncConfig.from_env(library_root)
    if not cfg:
        raise RuntimeError(
            "B-roll sync not configured. Set CROSSPOST_S3_* (or BROLL_S3_*) credentials."
        )
    cfg.library_root.mkdir(parents=True, exist_ok=True)
    remote = _list_remote_keys(cfg)
    client = _client(cfg)
    uploaded = 0
    skipped = 0
    bytes_up = 0

    for path in sorted(_iter_local_files(cfg.library_root)):
        key = _key_for(cfg, path)
        size = path.stat().st_size
        if remote.get(key) == size:
            skipped += 1
            continue
        log.info("Upload %s → s3://%s/%s (%s MB)", path.name, cfg.bucket, key, round(size / 1e6, 1))
        if dry_run:
            uploaded += 1
            bytes_up += size
            continue
        client.upload_file(str(path), cfg.bucket, key)
        uploaded += 1
        bytes_up += size

    return {
        "action": "upload",
        "uploaded": uploaded,
        "skipped": skipped,
        "bytes": bytes_up,
        "bucket": cfg.bucket,
        "prefix": cfg.prefix,
        "dry_run": dry_run,
    }


def download_library(
    *,
    library_root: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    cfg = SyncConfig.from_env(library_root)
    if not cfg:
        raise RuntimeError(
            "B-roll sync not configured. Set CROSSPOST_S3_* (or BROLL_S3_*) credentials."
        )
    cfg.library_root.mkdir(parents=True, exist_ok=True)
    remote = _list_remote_keys(cfg)
    client = _client(cfg)
    downloaded = 0
    skipped = 0
    bytes_down = 0

    for key, size in sorted(remote.items()):
        rel = key[len(cfg.prefix.rstrip("/")) + 1 :]
        if not rel:
            continue
        dest = cfg.library_root / rel
        if dest.exists() and dest.stat().st_size == size:
            skipped += 1
            continue
        log.info("Download s3://%s/%s → %s (%s MB)", cfg.bucket, key, dest, round(size / 1e6, 1))
        if dry_run:
            downloaded += 1
            bytes_down += size
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(cfg.bucket, key, str(dest))
        downloaded += 1
        bytes_down += size

    return {
        "action": "download",
        "downloaded": downloaded,
        "skipped": skipped,
        "bytes": bytes_down,
        "remote_objects": len(remote),
        "bucket": cfg.bucket,
        "prefix": cfg.prefix,
        "dry_run": dry_run,
        "library": str(cfg.library_root),
    }


def ensure_library_on_start(
    *,
    min_local_clips: int = 5,
) -> Optional[dict]:
    """
    Called by worker. If S3 is configured and local library is thin / empty,
    pull missing objects. No-op when sync env missing.
    """
    flag = os.getenv("BROLL_SYNC_ON_START", "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return None
    cfg = SyncConfig.from_env()
    if not cfg:
        log.info("B-roll sync skipped (no S3 credentials)")
        return None

    local_mp4 = [
        p
        for p in cfg.library_root.rglob("*.mp4")
        if p.is_file() and not _should_skip(p, cfg.library_root)
    ]
    log.info(
        "B-roll library: %s local clips at %s — syncing missing from s3://%s/%s",
        len(local_mp4),
        cfg.library_root,
        cfg.bucket,
        cfg.prefix,
    )
    result = download_library(library_root=cfg.library_root)
    after = [
        p
        for p in cfg.library_root.rglob("*.mp4")
        if p.is_file() and not _should_skip(p, cfg.library_root)
    ]
    result["local_clips_after"] = len(after)
    if len(after) < min_local_clips:
        log.warning(
            "B-roll library still thin (%s clips). Upload from PC: "
            "python scripts/sync_broll_library.py --upload",
            len(after),
        )
    else:
        log.info("B-roll ready: %s clips", len(after))
    return result
