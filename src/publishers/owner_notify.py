"""Compact owner Telegram status lines — no post bodies, no media."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

from src.publishers.telegram_publisher import TelegramPublisher

TIER_UA = {
    "breaking": "BREAKING",
    "insight": "Insight",
    "strong": "Strong",
    "standard": "News",
    "skip": "Skip",
}

EDITORIAL_KIND = {
    "opinion": ("Threads", "opinion"),
    "question": ("Threads", "question"),
    "context": ("TG", "context"),
    "recap": ("Threads", "weekly recap"),
    "poll": ("TG", "poll"),
    "digest": ("TG", "digest"),
}

KIND_TAB = {
    "opinion": "threads",
    "question": "threads",
    "recap": "threads",
    "context": "telegram",
    "poll": "telegram",
    "digest": "telegram",
    "tiktok": "tiktok",
    "instagram": "instagram",
    "carousel": "instagram",
    "short": "short",
}


def owner_full_kit_enabled() -> bool:
    """Send MP4 + copy packs to owner chat (legacy noisy mode)."""
    return os.getenv("OWNER_FULL_KIT", "").strip().lower() in {"1", "true", "yes"}


def _clip(text: str, n: int = 52) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def format_tg_channel_status(
    *,
    tier: str,
    title: str,
    score: int,
    post_count: int,
    max_posts: int = 8,
) -> str:
    label = TIER_UA.get((tier or "").lower(), (tier or "News").title())
    head = _clip(title, 44)
    base = f"📢 TG channel · {label} · {score} · {post_count}/{max_posts}"
    return f"{base} · {head}" if head else base


def format_tg_poll_status(*, question: str) -> str:
    return f"📢 TG channel · poll · {_clip(question, 48)}"


def format_tg_digest_status() -> str:
    return "📢 TG channel · weekly digest posted"


def format_threads_pulse_posted(*, variant: str = "", url: str = "") -> str:
    kind = (variant or "news").replace("_", " ")
    line = f"🧵 Threads · {kind} posted"
    if url:
        line += f" · {url}"
    return line


def desk_public_url() -> str:
    return os.getenv("DESK_PUBLIC_URL", "").strip().rstrip("/")


def desk_deep_link(*, kind: str = "", item_id: str = "", tab: str = "") -> str:
    """Path or absolute URL to a desk tab/card. Empty host → relative /?tab=."""
    tab = tab or KIND_TAB.get(kind, "threads")
    query = f"tab={tab}"
    if item_id:
        query += f"&item={quote(str(item_id))}"
    path = f"/?{query}"
    base = desk_public_url()
    return f"{base}{path}" if base else path


def format_desk_editorial_ready(*, kind: str, title: str = "", item_id: str = "") -> str:
    platform, label = EDITORIAL_KIND.get(kind, ("Desk", kind))
    head = _clip(title, 40)
    line = f"💬 {platform} · {label} · desk ready"
    if head:
        line = f"{line} · {head}"
    if desk_public_url():
        line += f"\n{desk_deep_link(kind=kind, item_id=item_id)}"
    return line


def format_youtube_status(
    *,
    state: str,
    qa_score: Optional[int] = None,
    publish_hint: str = "",
    url: str = "",
) -> str:
    """state: unlisted | public | skip | error"""
    parts = ["📺 YouTube", state]
    if qa_score is not None:
        parts.append(f"QA {qa_score}")
    if publish_hint:
        parts.append(publish_hint)
    line = " · ".join(parts)
    if url:
        line += f"\n{url}"
    return line


def format_manual_platform_status(
    *,
    platform: str,
    detail: str = "desk ready",
    extra: str = "",
) -> str:
    icons = {
        "tiktok": "📱 TikTok",
        "instagram": "📸 IG Reel",
        "carousel": "🖼 Carousel",
        "threads": "🧵 Threads",
    }
    label = icons.get(platform, platform)
    line = f"{label} · {detail}"
    if extra:
        line += f" · {extra}"
    return line


def format_short_status_bundle(
    *,
    title: str,
    desk_url: str = "",
    qa_score: Optional[int] = None,
    youtube_url: str = "",
    youtube_state: str = "skip",
    publish_hint: str = "",
    carousel_slides: int = 0,
    copy_source: str = "",
    degraded: Optional[list[str]] = None,
) -> str:
    """One message: one line per platform that's ready or auto-done."""
    lines = [
        format_youtube_status(
            state=youtube_state,
            qa_score=qa_score,
            publish_hint=publish_hint,
            url=youtube_url,
        ),
        format_manual_platform_status(platform="tiktok"),
        format_manual_platform_status(platform="instagram"),
    ]
    if carousel_slides > 0:
        lines.append(
            format_manual_platform_status(
                platform="carousel",
                extra=f"{carousel_slides} slides",
            )
        )
    if copy_source:
        lines.append(f"✏️ Copy · {copy_source}")
    if degraded:
        lines.append("⚠ " + ", ".join(degraded))
    head = _clip(title, 56)
    if head:
        lines.append(f"📋 {head}")
    if desk_url:
        lines.append(f"Desk: {desk_url.rstrip('/')}/?tab=tiktok")
    return "\n".join(lines)


def notify_owner_status(
    publisher: TelegramPublisher,
    lines: list[str],
    *,
    desk_url: str = "",
    buttons=None,
) -> None:
    """Send compact status message(s). Skips empty lines."""
    cleaned = [line.strip() for line in lines if line and line.strip()]
    if not cleaned:
        return
    body = "\n".join(cleaned)
    if desk_url and "Desk:" not in body and "/?tab=" not in body:
        body += f"\nDesk: {desk_url.rstrip('/')}/"
    try:
        publisher.notify_owner(body, buttons=buttons)
    except Exception as exc:
        print(f"Owner status notify failed: {exc}")
        import logging

        logging.getLogger(__name__).warning("Owner Telegram ping failed: %s", exc)
    try:
        from src.desk.push import notify_desk_push

        first = cleaned[0]
        notify_desk_push(
            "Coin Wire",
            first[:160],
            url=desk_deep_link(kind="threads") if "Threads" in body else desk_deep_link(kind="telegram") if "TG" in body else "/",
            tag="cw-desk-owner",
        )
    except Exception as exc:
        print(f"Owner web push failed: {exc}")


# Backward-compatible aliases (tests / older imports)
def format_telegram_channel_notice(
    *,
    tier: str,
    title: str,
    score: int,
    post_count: int,
    max_posts: int = 8,
    reason: str = "",
    link: str = "",
) -> str:
    line = format_tg_channel_status(
        tier=tier,
        title=title,
        score=score,
        post_count=post_count,
        max_posts=max_posts,
    )
    if link:
        line += f"\n{link}"
    return line


def format_short_ready_notice(
    *,
    title: str,
    youtube_url: str = "",
    desk_url: str = "",
    qa_score: Optional[int] = None,
) -> str:
    state = "unlisted" if youtube_url else "rendered"
    return format_short_status_bundle(
        title=title,
        desk_url=desk_url,
        qa_score=qa_score,
        youtube_url=youtube_url,
        youtube_state=state,
        carousel_slides=0,
    )
