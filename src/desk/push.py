"""Web Push for Coin Wire desk PWA (iOS/Android when installed to home screen)."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "data" / "storage" / "coin_wire"
VAPID_FILE = STORAGE / "desk_vapid.json"
SUBS_FILE = STORAGE / "desk_push_subs.json"

_lock = threading.RLock()


def push_configured() -> bool:
    return bool(public_key())


def public_key() -> str:
    return str(_ensure_vapid().get("publicKey") or "")


def _private_key() -> str:
    return str(_ensure_vapid().get("privateKey") or "")


def _subject() -> str:
    return (
        os.getenv("DESK_VAPID_SUBJECT", "mailto:coinwire@local").strip()
        or "mailto:coinwire@local"
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


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
    env_pub = os.getenv("DESK_VAPID_PUBLIC", "").strip()
    env_priv = os.getenv("DESK_VAPID_PRIVATE", "").strip()
    if env_pub and env_priv:
        return {"publicKey": env_pub, "privateKey": env_priv}

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
        try:
            keys = _generate_vapid()
        except Exception as exc:
            log.warning("VAPID generate failed: %s", exc)
            return {}
        STORAGE.mkdir(parents=True, exist_ok=True)
        VAPID_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")
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
    with _lock:
        items = load_subscriptions()
        items = [item for item in items if item.get("endpoint") != endpoint]
        items.append(
            {
                "endpoint": endpoint,
                "keys": subscription.get("keys") or {},
                "expirationTime": subscription.get("expirationTime"),
            }
        )
        STORAGE.mkdir(parents=True, exist_ok=True)
        SUBS_FILE.write_text(
            json.dumps({"subscriptions": items[-20:]}, indent=2),
            encoding="utf-8",
        )


def remove_subscription(endpoint: str) -> None:
    with _lock:
        items = [item for item in load_subscriptions() if item.get("endpoint") != endpoint]
        STORAGE.mkdir(parents=True, exist_ok=True)
        SUBS_FILE.write_text(
            json.dumps({"subscriptions": items}, indent=2),
            encoding="utf-8",
        )


def notify_desk_push(
    title: str,
    body: str,
    *,
    url: str = "/",
) -> dict[str, Any]:
    """Send Web Push to all desk subscribers. No-op if not configured."""
    if not push_configured():
        return {"sent": 0, "reason": "push_disabled"}
    try:
        from pywebpush import webpush
    except ImportError:
        return {"sent": 0, "reason": "pywebpush_missing"}

    payload = json.dumps(
        {
            "title": title[:80],
            "body": body[:160],
            "url": url or "/",
        },
        ensure_ascii=False,
    )
    sent = 0
    for sub in load_subscriptions():
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=_private_key(),
                vapid_claims={"sub": _subject()},
            )
            sent += 1
        except Exception as exc:
            msg = str(exc)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {404, 410} or "410" in msg or "404" in msg:
                remove_subscription(str(sub.get("endpoint") or ""))
            log.warning("Desk push failed: %s", exc)
    return {"sent": sent}
