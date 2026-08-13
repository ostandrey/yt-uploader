"""Weekly caps and owner/channel jobs for editorial formats."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.content import editorial_copy
from src.content.editorial_log import append_event, events_since, format_events_list, load_log
from src.content.story_dedupe import titles_similar
from src.desk.catalog import _raw_editorial_items, write_editorial_items
from src.publishers.telegram_publisher import TelegramPublisher
from src.publishers.threads_publisher import ThreadsPublisher

from src.paths import coin_wire_storage

STATE_FILE = coin_wire_storage() / "editorial_weekly_state.json"


def _story_editorial_done(title: str) -> bool:
    """True if desk already has (or recently logged) copy for this story."""
    title = (title or "").strip()
    if not title:
        return False
    for item in _raw_editorial_items():
        text = str(item.get("text") or "")
        if text and titles_similar(title, text[:220]):
            return True
    for event in load_log()[-60:]:
        if event.get("kind") in {"opinion", "question", "context"} and titles_similar(
            title, str(event.get("title") or "")
        ):
            return True
    return False


def _week_key(tz_name: str) -> str:
    now = datetime.now(ZoneInfo(tz_name))
    return now.strftime("%G-W%V")


def _load_state(tz_name: str, path: Path = STATE_FILE) -> dict[str, Any]:
    week = _week_key(tz_name)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("week") == week:
                return data
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return {
        "week": week,
        "opinion": 0,
        "question": 0,
        "poll": 0,
        "context": 0,
        "digest": 0,
        "recap": 0,
    }


def _save_state(state: dict[str, Any], path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _editorial_cfg(config: dict) -> dict[str, Any]:
    return config.get("publishing", {}).get("editorial", {}) or {}


def _tz(config: dict) -> str:
    return config.get("automation", {}).get("timezone", "America/New_York")


def _push_desk_item(kind: str, label: str, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    import hashlib
    from datetime import datetime, timezone

    raw = _raw_editorial_items()
    item_id = "e-" + hashlib.sha1(f"{kind}:{text}".encode("utf-8")).hexdigest()[:10]
    raw.insert(
        0,
        {
            "id": item_id,
            "kind": kind,
            "label": label,
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "done": False,
        },
    )
    write_editorial_items(raw)
    try:
        from src.desk.push import notify_desk_push
        from src.publishers.owner_notify import desk_deep_link, format_desk_editorial_ready

        pushed = notify_desk_push(
            "Desk ready",
            format_desk_editorial_ready(kind=kind, item_id=item_id),
            url=desk_deep_link(kind=kind, item_id=item_id),
            tag=f"cw-desk-{item_id}",
        )
        print(
            f"Desk web push: reason={pushed.get('reason')} "
            f"sent={pushed.get('sent')} subs={pushed.get('subs')}"
        )
    except Exception as exc:
        print(f"Desk push (editorial) failed: {exc}")


def after_telegram_post(
    article: dict[str, Any],
    tier: str,
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Log the story and maybe queue opinion / question / context for the operator."""
    cfg = _editorial_cfg(config)
    tz_name = _tz(config)
    append_event(
        kind="telegram",
        title=str(article.get("title") or ""),
        summary=str(article.get("summary") or ""),
        tier=tier,
        article_hash=str(article.get("hash") or ""),
    )
    if dry_run:
        return {"queued": []}

    state = _load_state(tz_name)
    queued: list[str] = []
    article = {**article, "tier": tier}
    title = str(article.get("title") or "")
    if _story_editorial_done(title):
        return {"queued": [], "skipped": "story_already_covered"}

    if tier == "breaking" and cfg.get("context_on_breaking", True) and state.get("context", 0) < 4:
        text = editorial_copy.telegram_context(article)
        if text:
            _push_desk_item("context", "Telegram — контекст", text)
            append_event(
                kind="context",
                title=title,
                summary=str(article.get("summary") or ""),
                tier=tier,
                article_hash=str(article.get("hash") or ""),
            )
            state["context"] = int(state.get("context", 0)) + 1
            queued.append("context")

    opinion_cap = int(cfg.get("opinion_per_week", 3))
    question_cap = int(cfg.get("question_per_week", 3))
    seed = sum(ord(c) for c in str(article.get("hash") or article.get("title") or "x"))
    want_opinion = seed % 2 == 0
    if want_opinion and state.get("opinion", 0) < opinion_cap and tier in {"strong", "breaking", "insight"}:
        text = editorial_copy.opinion_hook(article)
        if text:
            _push_desk_item("opinion", "Threads — opinion hook", text)
            append_event(
                kind="opinion",
                title=title,
                summary=str(article.get("summary") or ""),
                tier=tier,
                article_hash=str(article.get("hash") or ""),
            )
            state["opinion"] = int(state.get("opinion", 0)) + 1
            queued.append("opinion")
    elif state.get("question", 0) < question_cap and tier in {"strong", "breaking", "insight"}:
        text = editorial_copy.question_post(article)
        if text:
            _push_desk_item("question", "Threads — питання", text)
            append_event(
                kind="question",
                title=title,
                summary=str(article.get("summary") or ""),
                tier=tier,
                article_hash=str(article.get("hash") or ""),
            )
            state["question"] = int(state.get("question", 0)) + 1
            queued.append("question")

    _save_state(state)
    return {"queued": queued}


def post_weekly_digest(
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    tz_name = _tz(config)
    state = _load_state(tz_name)
    if state.get("digest"):
        return {"posted": False, "reason": "already_this_week"}
    items = events_since(7, kinds={"telegram", "short"}, tz_name=tz_name)
    events_list = format_events_list(items, limit=5)
    text = editorial_copy.telegram_weekly_digest(events_list)
    if not text:
        return {"posted": False, "reason": "no_events"}
    if dry_run:
        return {"posted": False, "dry_run": True, "text": text}
    publisher.post_to_channel(text)
    state["digest"] = 1
    _save_state(state)
    append_event(kind="digest", title="Weekly digest")
    try:
        from src.publishers.owner_notify import format_tg_digest_status, notify_owner_status

        notify_owner_status(publisher, [format_tg_digest_status()])
    except Exception as exc:
        print(f"Editorial owner notify failed: {exc}")
    return {"posted": True, "text": text}


def post_threads_recap(
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    tz_name = _tz(config)
    state = _load_state(tz_name)
    if state.get("recap"):
        return {"posted": False, "reason": "already_this_week"}
    items = events_since(7, kinds={"telegram", "short"}, tz_name=tz_name)
    events_list = format_events_list(items, limit=5)
    text = editorial_copy.weekly_recap(events_list)
    if not text:
        return {"posted": False, "reason": "no_events"}
    _push_desk_item("recap", "Threads — weekly recap", text)
    threads = ThreadsPublisher()
    posted = False
    url = ""
    if not dry_run and threads.configured():
        try:
            result = threads.publish_text(text)
            posted = True
            url = str(result.get("url") or "")
        except Exception as exc:
            print(f"Threads recap publish failed: {exc}")
    if not dry_run:
        state["recap"] = 1
        _save_state(state)
        append_event(kind="recap", title="Threads weekly recap")
        try:
            from src.publishers.owner_notify import (
                format_desk_editorial_ready,
                format_threads_pulse_posted,
                notify_owner_status,
            )

            lines = [format_desk_editorial_ready(kind="recap", title="Weekly recap")]
            if posted:
                lines.append(format_threads_pulse_posted(variant="weekly recap", url=url))
            notify_owner_status(publisher, lines)
        except Exception as exc:
            print(f"Editorial owner notify failed: {exc}")
    return {"posted": posted, "text": text, "url": url, "dry_run": dry_run}


def post_telegram_poll(
    publisher: TelegramPublisher,
    config: dict,
    article: Optional[dict[str, Any]] = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    tz_name = _tz(config)
    state = _load_state(tz_name)
    cap = int(_editorial_cfg(config).get("poll_per_week", 3))
    if state.get("poll", 0) >= cap:
        return {"posted": False, "reason": "weekly_cap"}
    if not article:
        items = events_since(3, kinds={"telegram"}, tz_name=tz_name)
        if not items:
            return {"posted": False, "reason": "no_events"}
        article = {
            "title": items[-1].get("title") or "",
            "summary": items[-1].get("summary") or "",
        }
    poll = editorial_copy.telegram_poll(article)
    if not poll:
        return {"posted": False, "reason": "no_poll"}
    if dry_run:
        return {"posted": False, "dry_run": True, **poll}
    publisher.post_poll_to_channel(poll["question"], poll["options"])
    state["poll"] = int(state.get("poll", 0)) + 1
    _save_state(state)
    append_event(kind="poll", title=poll["question"])
    try:
        from src.publishers.owner_notify import format_tg_poll_status, notify_owner_status

        notify_owner_status(
            publisher,
            [format_tg_poll_status(question=poll["question"])],
        )
    except Exception as exc:
        print(f"Editorial owner notify failed: {exc}")
    return {"posted": True, **poll}
