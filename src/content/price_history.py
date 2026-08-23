"""Daily price archive for rules-based "Numbers that matter" posts."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from src.content.market_ticker import MarketQuote
from src.paths import coin_wire_storage

HISTORY_FILE = coin_wire_storage() / "price_history.json"
KEEP_DAYS = 120
COMPARE_SYMBOLS = ("BTC", "ETH", "SOL", "XRP", "BNB")
PRIMARY_SYMBOLS = ("BTC", "ETH")


def _path(path: Optional[Path] = None) -> Path:
    return path or HISTORY_FILE


def load_history(path: Optional[Path] = None) -> dict[str, dict[str, float]]:
    file = _path(path)
    if not file.exists():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    days = data.get("days") if isinstance(data, dict) else None
    if not isinstance(days, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for day, row in days.items():
        if not isinstance(row, dict):
            continue
        prices: dict[str, float] = {}
        for symbol, value in row.items():
            try:
                prices[str(symbol).upper()] = float(value)
            except (TypeError, ValueError):
                continue
        if prices:
            out[str(day)] = prices
    return out


def save_history(days: dict[str, dict[str, float]], path: Optional[Path] = None) -> None:
    file = _path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    trimmed = {day: prices for day, prices in sorted(days.items()) if day >= cutoff}
    payload = {"days": trimmed}
    file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def record_quotes(
    quotes: list[MarketQuote],
    day: str,
    *,
    path: Optional[Path] = None,
) -> dict[str, float]:
    """Upsert one calendar day of USD prints. Returns the stored row."""
    day = (day or "").strip()
    if not day or not quotes:
        return {}
    history = load_history(path)
    row = dict(history.get(day) or {})
    for quote in quotes:
        row[quote.symbol.upper()] = float(quote.price_usd)
    history[day] = row
    save_history(history, path)
    return row


def find_compare_day(
    history: dict[str, dict[str, float]],
    today: str,
    *,
    lookback_days: int = 7,
    slack_days: int = 2,
) -> Optional[str]:
    """Prefer exact today-lookback; else nearest available within ±slack."""
    try:
        today_d = date.fromisoformat(today)
    except ValueError:
        return None
    target = today_d - timedelta(days=lookback_days)
    candidates = [target + timedelta(days=offset) for offset in range(-slack_days, slack_days + 1)]
    # Prefer exact target, then closer offsets
    candidates.sort(key=lambda d: (abs((d - target).days), -d.toordinal()))
    for candidate in candidates:
        key = candidate.isoformat()
        if key in history and key != today:
            return key
    return None


def _format_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _pct_change(now: float, then: float) -> Optional[float]:
    if then <= 0:
        return None
    return ((now - then) / then) * 100.0


def build_numbers_compare(
    today_prices: dict[str, float],
    then_prices: dict[str, float],
    *,
    lookback_days: int = 7,
    min_abs_pct: float = 2.0,
    max_lines: int = 2,
) -> dict[str, Any]:
    """
    Rules-only compare. Empty text means SKIP (move too small / missing data).

    Prefer BTC/ETH when they clear the threshold; otherwise top movers by |Δ%|.
    """
    rows: list[tuple[str, float, float, float]] = []
    for symbol in COMPARE_SYMBOLS:
        now = today_prices.get(symbol)
        then = then_prices.get(symbol)
        if now is None or then is None:
            continue
        pct = _pct_change(now, then)
        if pct is None:
            continue
        rows.append((symbol, now, then, pct))

    if not rows:
        return {"text": "", "reason": "no_overlap", "moves": []}

    primary = [
        row for row in rows if row[0] in PRIMARY_SYMBOLS and abs(row[3]) >= min_abs_pct
    ]
    if primary:
        chosen = sorted(primary, key=lambda r: abs(r[3]), reverse=True)[:max_lines]
    else:
        movers = [row for row in rows if abs(row[3]) >= min_abs_pct]
        if not movers:
            return {"text": "", "reason": "below_threshold", "moves": rows}
        chosen = sorted(movers, key=lambda r: abs(r[3]), reverse=True)[:max_lines]

    lines: list[str] = []
    for symbol, now, then, pct in chosen:
        sign = "+" if pct >= 0 else ""
        lines.append(f"{symbol} {_format_price(now)} vs {_format_price(then)}")
        lines.append(f"{sign}{pct:.1f}% over {lookback_days} days.")
        lines.append("")
    # Drop trailing blank
    while lines and not lines[-1]:
        lines.pop()
    tag = "#bitcoin" if chosen[0][0] == "BTC" else f"#{chosen[0][0].lower()}"
    lines.append("")
    lines.append(tag)
    return {
        "text": "\n".join(lines),
        "reason": "ok",
        "moves": chosen,
    }


def format_numbers_that_matter(
    *,
    today: str,
    history: Optional[dict[str, dict[str, float]]] = None,
    path: Optional[Path] = None,
    lookback_days: int = 7,
    min_abs_pct: float = 2.0,
) -> dict[str, Any]:
    """Load archive and format a Numbers post, or return skip reason."""
    history = history if history is not None else load_history(path)
    today_prices = history.get(today) or {}
    if not today_prices:
        return {"text": "", "reason": "no_today", "compare_day": ""}
    compare_day = find_compare_day(history, today, lookback_days=lookback_days)
    if not compare_day:
        return {"text": "", "reason": "no_compare_day", "compare_day": ""}
    result = build_numbers_compare(
        today_prices,
        history[compare_day],
        lookback_days=lookback_days,
        min_abs_pct=min_abs_pct,
    )
    result["compare_day"] = compare_day
    return result
