"""Password + HMAC session cookie. No third-party auth deps."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

COOKIE_NAME = "cw_desk"
DEFAULT_TTL_SEC = 12 * 3600
_FAILS: dict[str, list[float]] = {}


def password() -> str:
    return os.getenv("DESK_PASSWORD", "").strip()


def secret() -> bytes:
    raw = os.getenv("DESK_SECRET", "").strip() or password()
    if not raw:
        raw = "desk-disabled"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def session_ttl_sec() -> int:
    hours = float(os.getenv("DESK_SESSION_HOURS", "12") or "12")
    return max(600, int(hours * 3600))


def enabled() -> bool:
    return bool(password())


def check_password(candidate: str) -> bool:
    expected = password()
    if not expected:
        return False
    return hmac.compare_digest(
        hashlib.sha256(expected.encode("utf-8")).digest(),
        hashlib.sha256((candidate or "").encode("utf-8")).digest(),
    )


def issue_session() -> str:
    exp = int(time.time()) + session_ttl_sec()
    nonce = secrets.token_hex(8)
    payload = f"{exp}.{nonce}"
    sig = hmac.new(secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session(token: str) -> bool:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return False
    exp_s, nonce, sig = parts
    if not exp_s.isdigit() or len(nonce) != 16 or len(sig) != 64:
        return False
    payload = f"{exp_s}.{nonce}"
    expect = hmac.new(secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return False
    return int(exp_s) >= int(time.time())


def login_allowed(ip: str, *, window_sec: int = 900, max_fails: int = 5) -> bool:
    now = time.time()
    hits = [t for t in _FAILS.get(ip, []) if now - t < window_sec]
    _FAILS[ip] = hits
    return len(hits) < max_fails


def record_fail(ip: str) -> None:
    _FAILS.setdefault(ip, []).append(time.time())


def parse_cookie(header: str) -> Optional[str]:
    if not header:
        return None
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value.strip()
    return None
