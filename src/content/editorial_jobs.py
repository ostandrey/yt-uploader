"""Weekly caps and owner/channel jobs for editorial formats."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.content import editorial_copy
from src.content.editorial_log import append_event, events_since, format_events_list, load_log
from src.content.market_ticker import fetch_market_quotes, format_market_snapshot
from src.content.news_filter import build_market_takeaway
from src.content.price_history import format_numbers_that_matter, record_quotes
from src.content import price_history as ph
from src.content.story_dedupe import titles_similar
from src.desk.catalog import _raw_editorial_items, write_editorial_items
from src.publishers.telegram_publisher import TelegramPublisher
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
        if event.get("kind") in {"opinion", "question", "context", "reflection"} and titles_similar(
            title, str(event.get("title") or "")
        ):
            return True
    return False


def _week_key(tz_name: str) -> str:
    now = datetime.now(ZoneInfo(tz_name))
    return now.strftime("%G-W%V")


def _load_state(tz_name: str, path: Optional[Path] = None) -> dict[str, Any]:
    path = path or STATE_FILE
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
        "reflection": 0,
        "snapshot_day": "",
        "numbers": 0,
        "numbers_day": "",
        "story_quote": 0,
        "opinion_entities": [],
        "digest_titles": [],
    }


def _save_state(state: dict[str, Any], path: Optional[Path] = None) -> None:
    path = path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _editorial_cfg(config: dict) -> dict[str, Any]:
    return config.get("publishing", {}).get("editorial", {}) or {}


def _tz(config: dict) -> str:
    return config.get("automation", {}).get("timezone", "America/New_York")


def _push_desk_item(kind: str, label: str, text: str) -> bool:
    """Queue editorial on desk. Returns True if the card is on desk (new or already queued)."""
    text = (text or "").strip()
    if not text:
        return False
    from src.desk import catalog
    from src.desk.items import DESK_QUEUED

    result = catalog.queue_editorial_item(kind, label, text)
    item_id = str(result.get("id") or "")
    if not result.get("created"):
        print(
            f"Desk item dedup skip: id={item_id} kind={kind} "
            f"status={result.get('status')} reason={result.get('reason')}"
        )
        return result.get("status") == DESK_QUEUED or result.get("reason") == "dedup"
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
    return True


_TIER_RANK = {"breaking": 4, "insight": 3, "strong": 2, "standard": 1}
_ENTITY = re.compile(
    r"\b(BlackRock|Fidelity|Coinbase|Binance|Grayscale|MicroStrategy|"
    r"SEC|CFTC|Fed|FOMC|OCC|FDIC|ESMA|FCA|Treasury|"
    r"Bitcoin|Ethereum|Solana|XRP|ETF)\b",
    re.I,
)
_REGULATORY = re.compile(
    r"\b(SEC|CFTC|Fed|FOMC|OCC|FDIC|ESMA|FCA|Treasury|committee|filing|rule)\b",
    re.I,
)
_FLOW = re.compile(r"\b(ETF|inflow|outflow|flow|BlackRock|Fidelity|Grayscale)\b", re.I)
_MONEY = re.compile(r"\$|\d+(?:\.\d+)?\s?%")


def _event_entity(item: dict[str, Any]) -> str:
    blob = f"{item.get('title') or ''} {item.get('summary') or ''}"
    match = _ENTITY.search(blob)
    if match:
        return match.group(1)
    title = str(item.get("title") or "").strip()
    return " ".join(title.split()[:2]) if title else "This"


def _norm_entity(name: str) -> str:
    aliases = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "the fed": "fed",
        "federal reserve": "fed",
    }
    return aliases.get(name.lower(), name.lower())


def _event_fact(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    summary = str(item.get("summary") or "").strip()
    if title:
        return title
    return summary.split(".")[0].strip() if summary else ""


def _event_bucket(item: dict[str, Any]) -> str:
    blob = f"{item.get('title') or ''} {item.get('summary') or ''}"
    if _REGULATORY.search(blob) and not _FLOW.search(blob):
        return "regulatory"
    if _FLOW.search(blob):
        return "flow"
    return "other"


def pick_reflection_pair(events: list[dict[str, Any]]) -> Optional[tuple[dict[str, Any], dict[str, Any]]]:
    usable = [item for item in events if _event_fact(item)]
    if len(usable) < 2:
        return None

    def _score(item: dict[str, Any]) -> tuple[int, int]:
        rank = _TIER_RANK.get(str(item.get("tier") or "").lower(), 0)
        money = 1 if _MONEY.search(_event_fact(item)) else 0
        return (rank, money)

    ranked = sorted(usable, key=_score, reverse=True)
    top = ranked[0]
    top_entity = _norm_entity(_event_entity(top))
    top_bucket = _event_bucket(top)
    secondary = None
    for item in ranked[1:]:
        if _norm_entity(_event_entity(item)) == top_entity:
            continue
        if _event_bucket(item) != top_bucket or top_bucket == "other":
            secondary = item
            if _event_bucket(item) != top_bucket:
                break
    if secondary is None:
        for item in ranked[1:]:
            if _norm_entity(_event_entity(item)) != top_entity:
                secondary = item
                break
    if secondary is None:
        return None
    return top, secondary


def latest_telegram_takeaway(tz_name: str = "America/New_York") -> str:
    for item in reversed(events_since(1, kinds={"telegram"}, tz_name=tz_name)):
        value = str(item.get("takeaway") or "").strip()
        if value:
            return value
    return ""


def week_banned_leads(tz_name: str) -> list[str]:
    banned: list[str] = []
    for item in events_since(7, kinds={"telegram", "opinion"}, tz_name=tz_name):
        for key in ("takeaway", "summary", "title"):
            value = str(item.get(key) or "").strip()
            if value:
                banned.append(value)
    for item in _raw_editorial_items():
        if item.get("kind") in {"opinion", "question", "recap"}:
            text = str(item.get("text") or "").strip()
            if text:
                banned.append(text)
    return banned


def post_market_snapshot(
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    tz_name = _tz(config)
    today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    state = _load_state(tz_name)
    if state.get("snapshot_day") == today:
        return {"posted": False, "reason": "already_today"}
    quotes = fetch_market_quotes(snapshot=True)
    text = format_market_snapshot(quotes, when=datetime.now(ZoneInfo(tz_name)))
    if not text:
        return {"posted": False, "reason": "no_quotes"}
    if dry_run:
        return {"posted": False, "dry_run": True, "text": text}
    record_quotes(quotes, today)
    try:
        publisher.post_to_channel(text)
    except Exception as exc:
        print(f"Market snapshot Telegram failed: {exc}")
        return {"posted": False, "reason": "telegram_failed"}
    state["snapshot_day"] = today
    _save_state(state)
    _push_desk_item("snapshot", "Threads — зріз ринку", text)
    try:
        from src.media.ig_story import ensure_story_backgrounds

        ensure_story_backgrounds()
    except Exception as exc:
        print(f"Story background refresh failed: {exc}")
    append_event(kind="snapshot", title="Market snapshot")
    try:
        from src.publishers.owner_notify import format_desk_editorial_ready, notify_owner_status

        notify_owner_status(
            publisher,
            [format_desk_editorial_ready(kind="snapshot", title="Market snapshot")],
        )
    except Exception as exc:
        print(f"Snapshot owner notify failed: {exc}")
    return {"posted": True, "text": text}


def post_numbers_that_matter(
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Rules-based 7-day price contrast for Threads desk.
    Zero LLM. Skip when moves are flat or archive is thin.
    Does not post to Telegram channel (daily snapshot already covers the print).
    """
    tz_name = _tz(config)
    editorial = _editorial_cfg(config)
    if not editorial.get("numbers_that_matter", True):
        return {"posted": False, "reason": "disabled"}
    today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    state = _load_state(tz_name)
    if state.get("numbers_day") == today:
        return {"posted": False, "reason": "already_today"}
    cap = int(editorial.get("numbers_per_week", 3) or 3)
    if int(state.get("numbers", 0)) >= cap:
        return {"posted": False, "reason": "week_cap"}

    quotes = fetch_market_quotes(snapshot=True)
    if not quotes:
        return {"posted": False, "reason": "no_quotes"}
    if not dry_run:
        record_quotes(quotes, today)

    min_pct = float(editorial.get("numbers_min_pct", 2.0) or 2.0)
    lookback = int(editorial.get("numbers_lookback_days", 7) or 7)

    history = ph.load_history()
    if dry_run:
        # Preview with today's live prints without writing yet
        row = {q.symbol.upper(): float(q.price_usd) for q in quotes}
        history = dict(history)
        history[today] = row
    built = format_numbers_that_matter(
        today=today,
        history=history,
        lookback_days=lookback,
        min_abs_pct=min_pct,
    )
    text = str(built.get("text") or "").strip()
    if not text:
        return {
            "posted": False,
            "reason": str(built.get("reason") or "skip"),
            "compare_day": built.get("compare_day") or "",
        }
    if dry_run:
        return {
            "posted": False,
            "dry_run": True,
            "text": text,
            "compare_day": built.get("compare_day") or "",
        }

    state["numbers"] = int(state.get("numbers", 0)) + 1
    state["numbers_day"] = today
    _save_state(state)
    _push_desk_item("numbers", "Threads — numbers", text)
    append_event(kind="numbers", title="Numbers that matter")
    try:
        from src.publishers.owner_notify import format_desk_editorial_ready, notify_owner_status

        notify_owner_status(
            publisher,
            [format_desk_editorial_ready(kind="numbers", title="Numbers that matter")],
        )
    except Exception as exc:
        print(f"Numbers owner notify failed: {exc}")
    return {
        "posted": True,
        "text": text,
        "compare_day": built.get("compare_day") or "",
    }


def post_threads_reflection(
    publisher: TelegramPublisher,
    config: dict,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    tz_name = _tz(config)
    state = _load_state(tz_name)
    if state.get("reflection"):
        return {"posted": False, "reason": "already_this_week"}
    opinion_cap = int(_editorial_cfg(config).get("opinion_per_week", 3))
    if int(state.get("opinion", 0)) >= opinion_cap:
        return {"posted": False, "reason": "opinion_cap"}
    items = events_since(7, kinds={"telegram", "short"}, tz_name=tz_name)
    pair = pick_reflection_pair(items)
    if not pair:
        return {"posted": False, "reason": "need_two_stories"}
    top, secondary = pair
    banned = week_banned_leads(tz_name)
    text = editorial_copy.weekly_reflection(
        _event_entity(top),
        _event_fact(top),
        _event_entity(secondary),
        _event_fact(secondary),
        banned=banned,
    )
    if not text:
        return {"posted": False, "reason": "no_copy"}
    _push_desk_item("reflection", "Threads — рефлексія тижня", text)
    if dry_run:
        return {"posted": False, "dry_run": True, "text": text}
    state["reflection"] = 1
    state["opinion"] = int(state.get("opinion", 0)) + 1
    _save_state(state)
    append_event(kind="reflection", title="Threads weekly reflection")
    try:
        from src.publishers.owner_notify import format_desk_editorial_ready, notify_owner_status

        notify_owner_status(
            publisher,
            [format_desk_editorial_ready(kind="reflection", title="Weekly reflection")],
        )
    except Exception as exc:
        print(f"Editorial owner notify failed: {exc}")
    return {"posted": False, "text": text, "url": ""}


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
        extra={"takeaway": build_market_takeaway(article)},
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
    entity = _norm_entity(_event_entity(article))
    used_entities = {
        _norm_entity(str(x)) for x in (state.get("opinion_entities") or []) if str(x).strip()
    }
    # Diversity: at most one opinion per entity/topic per week.
    if entity and entity in used_entities:
        want_opinion = False
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
            entities = list(state.get("opinion_entities") or [])
            if entity and entity not in {_norm_entity(str(x)) for x in entities}:
                entities.append(entity)
            state["opinion_entities"] = entities
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


def _filter_recap_items(
    items: list[dict[str, Any]],
    digest_titles: list[str],
) -> list[dict[str, Any]]:
    """Drop Monday digest top-3 stories from Friday Threads recap when alternatives exist."""
    blocked = [str(t).strip() for t in (digest_titles or [])[:3] if str(t).strip()]
    if not blocked:
        return items
    kept: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        if any(titles_similar(title, ban) for ban in blocked):
            continue
        kept.append(item)
    # Prefer non-digest stories even if fewer than 5; empty → keep original.
    return kept if kept else items


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
    state["digest_titles"] = [
        str(item.get("title") or "").strip()
        for item in items[-5:]
        if str(item.get("title") or "").strip()
    ][:3]
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
    recap_result: dict[str, Any]
    if state.get("recap"):
        recap_result = {"posted": False, "reason": "already_this_week", "dry_run": dry_run}
    else:
        items = events_since(7, kinds={"telegram", "short"}, tz_name=tz_name)
        items = _filter_recap_items(items, list(state.get("digest_titles") or []))
        events_list = format_events_list(items, limit=5)
        text = editorial_copy.weekly_recap(events_list)
        if not text:
            recap_result = {"posted": False, "reason": "no_events", "dry_run": dry_run}
        else:
            _push_desk_item("recap", "Threads — weekly recap", text)
            # Desk-only: operator posts to Threads. No Graph auto-publish.
            if not dry_run:
                state["recap"] = 1
                _save_state(state)
                append_event(kind="recap", title="Threads weekly recap")
                try:
                    from src.publishers.owner_notify import (
                        format_desk_editorial_ready,
                        notify_owner_status,
                    )

                    notify_owner_status(
                        publisher,
                        [format_desk_editorial_ready(kind="recap", title="Weekly recap")],
                    )
                except Exception as exc:
                    print(f"Editorial owner notify failed: {exc}")
            recap_result = {
                "posted": False,
                "desk_queued": True,
                "text": text,
                "url": "",
                "dry_run": dry_run,
            }
    if _editorial_cfg(config).get("threads_reflection", True):
        recap_result["reflection"] = post_threads_reflection(
            publisher, config, dry_run=dry_run
        )
    return recap_result


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
