"""Web Push for Coin Wire desk PWA (iOS/Android when installed to home screen)."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.paths import coin_wire_storage

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
STORAGE = coin_wire_storage()
VAPID_FILE = STORAGE / "desk_vapid.json"
SUBS_FILE = STORAGE / "desk_push_subs.json"
LAST_FILE = STORAGE / "desk_push_last.json"

_lock = threading.RLock()


def push_configured() -> bool:
    return bool(public_key())


def public_key() -> str:
    return str(_ensure_vapid().get("publicKey") or "")


def _private_key() -> str:
    return _pad_b64(str(_ensure_vapid().get("privateKey") or ""))


def _subject() -> str:
    # Push services reject odd subjects like mailto:…@local
    return (
        os.getenv("DESK_VAPID_SUBJECT", "").strip()
        or os.getenv("VAPID_SUBJECT", "").strip()
        or "mailto:coinwire@example.com"
    )


def _env_vapid() -> dict[str, str]:
    pub = (
        os.getenv("DESK_VAPID_PUBLIC", "").strip()
        or os.getenv("VAPID_PUBLIC_KEY", "").strip()
    )
    priv = (
        os.getenv("DESK_VAPID_PRIVATE", "").strip()
        or os.getenv("VAPID_PRIVATE_KEY", "").strip()
    )
    if pub and priv:
        return {"publicKey": pub, "privateKey": priv}
    return {}


def subscription_debug_info(subscription: dict[str, Any]) -> dict[str, Any]:
    endpoint = str(subscription.get("endpoint") or "")
    keys = subscription.get("keys") or {}
    return {
        "has_endpoint": bool(endpoint),
        "endpoint_prefix": endpoint[:35],
        "has_p256dh": bool(keys.get("p256dh")),
        "has_auth": bool(keys.get("auth")),
    }


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pad_b64(value: str) -> str:
    raw = (value or "").strip()
    return raw + ("=" * ((4 - len(raw) % 4) % 4))


def _generate_vapid() -> dict[str, str]:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return {"publicKey": _b64(pub_bytes), "privateKey": _b64(priv_bytes)}


def _ensure_vapid() -> dict[str, str]:
    env_keys = _env_vapid()
    if env_keys:
        return env_keys

    with _lock:
        if VAPID_FILE.exists():
            try:
                data = json.loads(VAPID_FILE.read_text(encoding="utf-8"))
                if data.get("publicKey") and data.get("privateKey"):
                    return {
                        "publicKey": str(data["publicKey"]),
                        "privateKey": str(data["privateKey"]),
                    }
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
        try:
            keys = _generate_vapid()
        except Exception as exc:
            log.warning("VAPID generate failed: %s", exc)
            return {}
        try:
            STORAGE.mkdir(parents=True, exist_ok=True)
            VAPID_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("VAPID persist failed (keys still in memory this process): %s", exc)
        if on_railway:
            log.warning(
                "Generated ephemeral VAPID keys. Set DESK_VAPID_PUBLIC + "
                "DESK_VAPID_PRIVATE (or mount /app/data) or iOS push dies after deploy."
            )
        return keys


def load_subscriptions() -> list[dict[str, Any]]:
    if not SUBS_FILE.exists():
        return []
    try:
        data = json.loads(SUBS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("subscriptions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("endpoint")]


def save_subscription(subscription: dict[str, Any]) -> None:
    endpoint = str(subscription.get("endpoint") or "")
    if not endpoint:
        return
    keys = subscription.get("keys") or {}
    if not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("subscription missing keys")
    with _lock:
        items = load_subscriptions()
        items = [item for item in items if item.get("endpoint") != endpoint]
        items.append(
            {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": str(keys.get("p256dh") or ""),
                    "auth": str(keys.get("auth") or ""),
                },
                "expirationTime": subscription.get("expirationTime"),
            }
        )
        STORAGE.mkdir(parents=True, exist_ok=True)
        SUBS_FILE.write_text(
            json.dumps({"subscriptions": items[-20:]}, indent=2),
            encoding="utf-8",
        )
        log.info("Push subscription saved: %s", subscription_debug_info(subscription))


def remove_subscription(endpoint: str) -> None:
    with _lock:
        items = [item for item in load_subscriptions() if item.get("endpoint") != endpoint]
        STORAGE.mkdir(parents=True, exist_ok=True)
        SUBS_FILE.write_text(
            json.dumps({"subscriptions": items}, indent=2),
            encoding="utf-8",
        )


def vapid_source() -> str:
    if _env_vapid():
        return "env"
    if VAPID_FILE.exists():
        return "file"
    return "generated"


def _remember_last(result: dict[str, Any]) -> None:
    payload = {
        **result,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        STORAGE.mkdir(parents=True, exist_ok=True)
        LAST_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Push last-result persist failed: %s", exc)


def push_status() -> dict[str, Any]:
    last: dict[str, Any] = {}
    if LAST_FILE.exists():
        try:
            loaded = json.loads(LAST_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                last = loaded
        except (OSError, json.JSONDecodeError, TypeError):
            last = {}
    return {
        "configured": push_configured(),
        "subs": len(load_subscriptions()),
        "vapid_file": VAPID_FILE.exists(),
        "vapid_source": vapid_source(),
        "subs_file": SUBS_FILE.exists(),
        "storage": str(STORAGE),
        "subject": _subject(),
        "last": {
            "reason": last.get("reason"),
            "sent": last.get("sent"),
            "failed": last.get("failed"),
            "ts": last.get("ts"),
            "errors": last.get("errors") or [],
        },
    }


def notify_desk_push(
    title: str,
    body: str,
    *,
    url: str = "/",
    tag: str = "cw-desk-push",
) -> dict[str, Any]:
    """Send Web Push to all desk subscribers. No-op if not configured."""
    if not push_configured():
        result = {"sent": 0, "failed": 0, "reason": "push_disabled", "errors": []}
        _remember_last(result)
        return result
    try:
        from pywebpush import webpush
    except ImportError:
        result = {"sent": 0, "failed": 0, "reason": "pywebpush_missing", "errors": []}
        _remember_last(result)
        return result

    subs = load_subscriptions()
    if not subs:
        result = {"sent": 0, "failed": 0, "reason": "no_subscriptions", "errors": []}
        _remember_last(result)
        log.warning("Web Push skipped: no subscriptions at %s", SUBS_FILE)
        _alert_push_miss(title, body, result)
        return result

    payload = json.dumps(
        {
            "title": title[:80],
            "body": body[:160],
            "url": url or "/",
            "tag": tag[:80] if tag else "cw-desk-push",
        },
        ensure_ascii=False,
    )
    sent = 0
    failed = 0
    errors: list[str] = []
    for sub in subs:
        endpoint = str(sub.get("endpoint") or "")
        try:
            response = webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=_private_key(),
                vapid_claims={"sub": _subject()},
                ttl=86400,
                timeout=20,
                headers={"Urgency": "high"},
            )
            status = getattr(response, "status_code", None) or 201
            log.info(
                "Web Push sent: status=%s %s vapid=%s",
                status,
                subscription_debug_info(sub),
                vapid_source(),
            )
            sent += 1
        except Exception as exc:
            failed += 1
            msg = str(exc)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            body_txt = getattr(getattr(exc, "response", None), "text", "") or ""
            log.warning(
                "Web Push failed: status=%s body=%s %s",
                status,
                str(body_txt)[:200],
                subscription_debug_info(sub),
            )
            if status in {404, 410} or "410" in msg or "404" in msg:
                remove_subscription(endpoint)
                errors.append(f"gone:{status or '4xx'}")
            else:
                errors.append(f"{status or 'err'}:{msg[:120]}")
    result = {
        "sent": sent,
        "failed": failed,
        "reason": "ok" if sent else "all_failed",
        "errors": errors[:5],
        "subs": len(subs),
        "vapid_source": vapid_source(),
    }
    _remember_last(result)
    if sent == 0:
        _alert_push_miss(title, body, result)
    return result


def _alert_push_miss(title: str, body: str, result: dict[str, Any]) -> None:
    """Operator ping when desk push did not land (silent fail otherwise)."""
    reason = str(result.get("reason") or "")
    if reason not in {"no_subscriptions", "all_failed"}:
        return
    # Rate-limit: every editorial miss would otherwise spam Telegram.
    try:
        gate = STORAGE / "desk_push_alert_gate.json"
        now = datetime.now(timezone.utc)
        last: dict[str, Any] = {}
        if gate.exists():
            try:
                loaded = json.loads(gate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    last = loaded
            except (OSError, json.JSONDecodeError):
                last = {}
        prev = str(last.get(reason) or "")
        if prev:
            try:
                prev_dt = datetime.fromisoformat(prev.replace("Z", "+00:00"))
                if prev_dt.tzinfo is None:
                    prev_dt = prev_dt.replace(tzinfo=timezone.utc)
                if (now - prev_dt).total_seconds() < 1800:
                    log.warning("Desk push miss suppressed (rate): %s", reason)
                    return
            except ValueError:
                pass
        last[reason] = now.isoformat()
        gate.parent.mkdir(parents=True, exist_ok=True)
        gate.write_text(json.dumps(last, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Push alert gate failed: %s", exc)
    try:
        from src.publishers.telegram_publisher import TelegramPublisher

        pub = TelegramPublisher()
        if not (pub.bot_token and pub.notify_chat_id):
            return
        err = ", ".join(result.get("errors") or [])[:160]
        lines = [
            f"⚠️ Desk push miss: {reason}",
            f"title={title[:60]}",
            f"subs={result.get('subs')} failed={result.get('failed')}",
        ]
        if err:
            lines.append(err)
        pub.notify_owner("\n".join(lines))
        log.warning("Alerted owner about desk push miss (%s)", reason)
    except Exception as exc:
        log.warning("Could not alert owner about push miss: %s", exc)