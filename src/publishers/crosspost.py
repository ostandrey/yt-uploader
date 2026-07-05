"""
Cross-post a rendered Short to TikTok, Instagram, and Threads.

Each platform is independent — one failure does not block the others.
  - TikTok: local MP4 upload
  - Instagram: Reels + feed image/carousel (needs R2 for public URLs)
  - Threads: text-only news posts (no video)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from src.publishers.captions import (
    build_caption,
    build_threads_text,
    pick_engagement_question,
    should_add_engagement_question,
)
from src.media.instagram_feed_image import create_instagram_feed_assets
from src.publishers.instagram_publisher import InstagramPublisher
from src.publishers.media_host import (
    media_host_configured,
    upload_public_file,
    upload_public_video,
)
from src.publishers.threads_publisher import ThreadsPublisher
from src.publishers.tiktok_publisher import TikTokPublisher

log = logging.getLogger(__name__)


def _platform_enabled(config: dict, name: str) -> bool:
    return bool(config.get("publishing", {}).get(name, {}).get("enabled", False))


def _platform_cfg(config: dict, name: str) -> dict:
    return config.get("publishing", {}).get(name, {}) or {}


def _threads_mode(config: dict) -> str:
    mode = str(_platform_cfg(config, "threads").get("mode", "text")).lower()
    if mode in ("text", "text_only", "news"):
        return "text"
    return mode


def _instagram_wants_reel(config: dict) -> bool:
    cfg = _platform_cfg(config, "instagram")
    return bool(cfg.get("reel", True))


def _instagram_wants_feed(config: dict) -> bool:
    cfg = _platform_cfg(config, "instagram")
    return bool(cfg.get("feed_image", True) or cfg.get("carousel", True))


def _instagram_use_carousel(config: dict, seed: str) -> bool:
    cfg = _platform_cfg(config, "instagram")
    if not cfg.get("carousel", True):
        return False
    rate = float(cfg.get("carousel_rate", 0.35))
    return should_add_engagement_question(seed, rate)


def run_crosspost(
    video_path: Path,
    title: str,
    description: str = "",
    *,
    config: Optional[dict] = None,
    youtube_url: str = "",
    thumbnail_path: Optional[Path] = None,
    keywords: Optional[list[str]] = None,
    seed: str = "",
    threads_text_override: str = "",
    ig_caption_override: str = "",
) -> dict[str, Any]:
    """
    Post to all enabled platforms. Returns:
      {
        "results": {"tiktok": {...}, "instagram_reel": {...}, ...},
        "errors": {"instagram_reel": "msg", ...},
        "skipped": {"threads": "reason", ...},
      }
    """
    config = config or {}
    video_path = Path(video_path)
    thumbnail_path = Path(thumbnail_path) if thumbnail_path else None
    seed = seed or title
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    skipped: dict[str, str] = {}

    want_tiktok = _platform_enabled(config, "tiktok")
    want_ig = _platform_enabled(config, "instagram")
    want_threads = _platform_enabled(config, "threads")

    if not any((want_tiktok, want_ig, want_threads)):
        return {"results": results, "errors": errors, "skipped": skipped}

    caption = build_caption(title, description)
    threads_cfg = _platform_cfg(config, "threads")
    if threads_text_override.strip():
        threads_text = threads_text_override.strip()
        if youtube_url and youtube_url not in threads_text:
            threads_text = f"{threads_text}\n\n{youtube_url}"[:500]
    else:
        engagement = ""
        if threads_cfg.get("engagement_questions", True):
            rate = float(threads_cfg.get("question_rate", 0.35))
            if should_add_engagement_question(seed, rate):
                engagement = pick_engagement_question(seed)
        threads_text = build_threads_text(
            title,
            description,
            youtube_url=youtube_url,
            engagement_question=engagement,
        )

    ig_caption = ig_caption_override.strip() or caption

    # --- TikTok (local file) ---
    if want_tiktok:
        tt_cfg = _platform_cfg(config, "tiktok")
        privacy = tt_cfg.get("privacy_level", "PUBLIC_TO_EVERYONE")
        publisher = TikTokPublisher(privacy_level=privacy)
        if not publisher.configured():
            skipped["tiktok"] = "missing TIKTOK_ACCESS_TOKEN"
        else:
            try:
                print("[crosspost] TikTok: uploading...")
                results["tiktok"] = publisher.upload_video(video_path, ig_caption)
                print(f"[crosspost] TikTok: {results['tiktok'].get('status')}")
            except Exception as exc:
                log.exception("TikTok crosspost failed")
                errors["tiktok"] = str(exc)
                print(f"[crosspost] TikTok FAILED: {exc}")

    # --- Threads (text-only by default) ---
    if want_threads:
        if _threads_mode(config) != "text":
            skipped["threads"] = f"unsupported mode: {_threads_mode(config)}"
        else:
            threads = ThreadsPublisher()
            if not threads.configured():
                skipped["threads"] = "missing THREADS_ACCESS_TOKEN / THREADS_USER_ID"
            else:
                try:
                    print("[crosspost] Threads: publishing text...")
                    results["threads"] = threads.publish_text(threads_text)
                    print(f"[crosspost] Threads: {results['threads'].get('url')}")
                except Exception as exc:
                    log.exception("Threads crosspost failed")
                    errors["threads"] = str(exc)
                    print(f"[crosspost] Threads FAILED: {exc}")

    # --- Instagram (Reels + feed image/carousel) ---
    if not want_ig:
        return {"results": results, "errors": errors, "skipped": skipped}

    ig = InstagramPublisher()
    if not ig.configured():
        skipped["instagram"] = "missing META_ACCESS_TOKEN / INSTAGRAM_USER_ID"
        return {"results": results, "errors": errors, "skipped": skipped}

    if not media_host_configured():
        if _instagram_wants_reel(config):
            skipped["instagram_reel"] = "media host not configured (CROSSPOST_S3_*)"
        if _instagram_wants_feed(config):
            skipped["instagram_feed"] = "media host not configured (CROSSPOST_S3_*)"
        return {"results": results, "errors": errors, "skipped": skipped}

    public_video_url: Optional[str] = None
    if _instagram_wants_reel(config):
        try:
            print("[crosspost] Uploading Reel video for Instagram...")
            public_video_url = upload_public_video(video_path)
        except Exception as exc:
            log.exception("Instagram Reel media upload failed")
            errors["instagram_reel"] = str(exc)
            skipped["instagram_reel"] = f"media upload failed: {exc}"

    if public_video_url:
        try:
            print("[crosspost] Instagram Reels: publishing...")
            results["instagram_reel"] = ig.publish_reel(public_video_url, ig_caption)
            print(f"[crosspost] Instagram Reel: {results['instagram_reel'].get('url')}")
        except Exception as exc:
            log.exception("Instagram Reel failed")
            errors["instagram_reel"] = str(exc)
            print(f"[crosspost] Instagram Reel FAILED: {exc}")

    if _instagram_wants_feed(config):
        try:
            feed_caption = ig_caption
            use_carousel = _instagram_use_carousel(config, seed)
            with tempfile.TemporaryDirectory(prefix="cw_ig_") as tmp:
                local_images = create_instagram_feed_assets(
                    title,
                    Path(tmp),
                    keywords=keywords,
                    carousel=use_carousel,
                    thumbnail_fallback=thumbnail_path,
                )
                if not local_images:
                    skipped["instagram_feed"] = (
                        "no stock image (PEXELS/PIXABAY keys?) and no thumbnail"
                    )
                else:
                    image_urls = [upload_public_file(path) for path in local_images]
                    if use_carousel and len(image_urls) >= 2:
                        print("[crosspost] Instagram carousel: publishing...")
                        results["instagram_feed"] = ig.publish_carousel(
                            image_urls,
                            feed_caption,
                        )
                    else:
                        print("[crosspost] Instagram feed image: publishing...")
                        results["instagram_feed"] = ig.publish_image(
                            image_urls[0],
                            feed_caption,
                        )
                    print(
                        f"[crosspost] Instagram feed: "
                        f"{results['instagram_feed'].get('url')}"
                    )
        except Exception as exc:
            log.exception("Instagram feed post failed")
            errors["instagram_feed"] = str(exc)
            print(f"[crosspost] Instagram feed FAILED: {exc}")

    return {"results": results, "errors": errors, "skipped": skipped}


def format_crosspost_summary(crosspost: dict[str, Any]) -> str:
    lines = ["Cross-post:"]
    for platform, data in (crosspost.get("results") or {}).items():
        url = data.get("url") or data.get("publish_id") or data.get("status") or "ok"
        fmt = data.get("format")
        label = f"{platform} ({fmt})" if fmt else platform
        lines.append(f"  OK {label}: {url}")
    for platform, reason in (crosspost.get("skipped") or {}).items():
        lines.append(f"  SKIP {platform}: {reason}")
    for platform, err in (crosspost.get("errors") or {}).items():
        lines.append(f"  FAIL {platform}: {err[:120]}")
    if len(lines) == 1:
        lines.append("  (no platforms enabled)")
    return "\n".join(lines)
