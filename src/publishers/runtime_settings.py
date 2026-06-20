"""
Runtime toggles (persisted on volume) — bot can change, env can hard-lock off.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = ROOT / "data" / "storage" / "coin_wire" / "runtime_settings.json"
BOT_STATE_FILE = ROOT / "data" / "storage" / "coin_wire" / "telegram_bot_state.json"


def _load_config() -> dict:
    with (ROOT / "config" / "coin_wire.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def env_auto_publish_lock() -> Optional[bool]:
    """Hard lock from Railway/.env. None = no env override."""
    env = os.getenv("YOUTUBE_AUTO_PUBLISH", "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    if env in ("1", "true", "yes", "on"):
        return True
    return None


def get_runtime_auto_publish() -> Optional[bool]:
    value = _read_json(SETTINGS_FILE).get("auto_publish")
    if value is None:
        return None
    return bool(value)


def set_runtime_auto_publish(enabled: bool) -> None:
    data = _read_json(SETTINGS_FILE)
    data["auto_publish"] = enabled
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = "telegram_bot"
    _write_json(SETTINGS_FILE, data)


def auto_publish_resolved(config: Optional[dict] = None) -> tuple[bool, str]:
    """
    Returns (enabled, source) where source explains who decided.
    """
    lock = env_auto_publish_lock()
    if lock is False:
        return False, "env_off"
    if lock is True:
        return True, "env_on"

    runtime = get_runtime_auto_publish()
    if runtime is not None:
        return runtime, "bot" if _read_json(SETTINGS_FILE).get("updated_by") == "telegram_bot" else "runtime"

    cfg = config or _load_config()
    default = bool(cfg.get("publishing", {}).get("youtube", {}).get("auto_publish_scheduled", False))
    return default, "yaml_default"


def get_bot_update_offset() -> int:
    return int(_read_json(BOT_STATE_FILE).get("update_offset", 0))


def set_bot_update_offset(offset: int) -> None:
    data = _read_json(BOT_STATE_FILE)
    data["update_offset"] = offset
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(BOT_STATE_FILE, data)
