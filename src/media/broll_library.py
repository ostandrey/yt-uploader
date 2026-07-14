"""
Local B-roll clip library — zero API latency, used before Pexels/Pixabay.

Drop portrait MP4s into:
  data/assets/broll_library/{category}/*.mp4

Clips with reject:true in *.meta.json (or under _rejected/) are skipped.
Fill via: python scripts/fill_broll_library.py

Pick prefers YOLO flags (has_screen / good_for_hook) and rotates via
data/storage/coin_wire/used_broll_clips.json.

Categories: bitcoin, ethereum, macro, regulation, security, defi, default
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIBRARY = ROOT / "data" / "assets" / "broll_library"
USED_CLIPS_FILE = ROOT / "data" / "storage" / "coin_wire" / "used_broll_clips.json"
USED_TRIM = 300

FLAG_WEIGHTS = {
    "good_for_hook": 100,
    "has_screen": 50,
    "office_vibe": 20,
    "avoid_as_hook": -80,
}


def _is_rejected(mp4: Path) -> bool:
    if "_rejected" in mp4.parts:
        return True
    meta = mp4.with_suffix(".meta.json")
    if not meta.exists():
        return False
    try:
        return bool(json.loads(meta.read_text(encoding="utf-8")).get("reject"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _load_meta(mp4: Path) -> Dict[str, Any]:
    meta_path = mp4.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def clip_id(mp4: Path, meta: Optional[Dict[str, Any]] = None) -> str:
    meta = meta if meta is not None else _load_meta(mp4)
    src = meta.get("source")
    sid = meta.get("source_id")
    if src and sid:
        return f"{src}:{sid}"
    return mp4.stem


def score_clip(mp4: Path, *, prefer_hook: bool = False) -> Tuple[int, Dict[str, Any]]:
    meta = _load_meta(mp4)
    flags = list(meta.get("flags") or [])
    score = 0
    for flag in flags:
        score += FLAG_WEIGHTS.get(flag, 0)
    probe = meta.get("qa", {}).get("probe") or meta.get("probe") or {}
    if probe.get("portrait") or (
        int(probe.get("height") or 0) >= int(probe.get("width") or 1)
    ):
        score += 10
    if prefer_hook:
        if "good_for_hook" in flags:
            score += 40
        if "avoid_as_hook" in flags:
            score -= 40
        if "has_screen" in flags:
            score += 15
    return score, meta


VALID_CATEGORIES = frozenset({
    "bitcoin", "ethereum", "macro", "regulation", "security", "defi", "default",
})

# Map search token / category aliases to library folder names.
CATEGORY_ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "fed": "macro",
    "federal": "macro",
    "reserve": "macro",
    "rates": "macro",
    "rate": "macro",
    "inflation": "macro",
    "etf": "macro",
    "market": "macro",
    "sec": "regulation",
    "regulation": "regulation",
    "regulatory": "regulation",
    "lawsuit": "regulation",
    "treasury": "macro",
    "hack": "security",
    "exploit": "security",
    "breach": "security",
    "defi": "defi",
    "tokenization": "defi",
    "stablecoin": "defi",
    "altcoin": "ethereum",
    "crypto": "bitcoin",
    "cryptocurrency": "bitcoin",
}


def normalize_category(category: str) -> str:
    key = category.lower().strip()
    if key in VALID_CATEGORIES:
        return key
    return CATEGORY_ALIASES.get(key, "default")


def list_library_clips(library_root: Path, category: str) -> list[Path]:
    library_root = library_root or DEFAULT_LIBRARY
    cat = normalize_category(category)
    folders = [library_root / cat]
    if cat != "default":
        folders.append(library_root / "default")

    clips: list[Path] = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.mp4")):
            if path.stat().st_size > 50_000 and not _is_rejected(path):
                clips.append(path)
    return clips


def load_recently_used_ids(path: Path = USED_CLIPS_FILE) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = data.get("ids") if isinstance(data, dict) else data
        return [str(x) for x in (ids or [])]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def mark_clip_used(mp4: Path, path: Path = USED_CLIPS_FILE) -> None:
    cid = clip_id(mp4)
    used = load_recently_used_ids(path)
    used = [u for u in used if u != cid]
    used.append(cid)
    used = used[-USED_TRIM:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ids": used,
                "updated": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def pick_local_clip(
    category: str,
    used_paths: Set[str],
    library_root: Optional[Path] = None,
    *,
    prefer_hook: bool = False,
    persist_rotation: bool = True,
) -> Optional[Path]:
    """
    Pick a local clip: higher YOLO/meta score first, avoid recent IDs + in-render paths.
    """
    root = library_root or DEFAULT_LIBRARY
    clips = list_library_clips(root, category)
    if not clips:
        return None

    recent = set(load_recently_used_ids()) if persist_rotation else set()
    scored: List[Tuple[int, Path]] = []
    for path in clips:
        resolved = str(path.resolve())
        if resolved in used_paths:
            continue
        score, meta = score_clip(path, prefer_hook=prefer_hook)
        cid = clip_id(path, meta)
        if cid in recent:
            score -= 60
        scored.append((score, path))

    if not scored:
        # All used in this render — allow revisit but still score
        for path in clips:
            score, _ = score_clip(path, prefer_hook=prefer_hook)
            scored.append((score, path))

    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][0]
    # Softmax-ish pool: near the top score
    pool = [p for s, p in scored if s >= best - 40][:8]
    if not pool:
        pool = [scored[0][1]]

    chosen = random.choice(pool)
    if persist_rotation:
        mark_clip_used(chosen)
    return chosen


def library_stats(library_root: Optional[Path] = None) -> dict[str, int]:
    root = library_root or DEFAULT_LIBRARY
    stats: dict[str, int] = {}
    for cat in VALID_CATEGORIES:
        folder = root / cat
        if not folder.is_dir():
            continue
        count = sum(
            1
            for path in folder.glob("*.mp4")
            if path.stat().st_size > 50_000 and not _is_rejected(path)
        )
        if count:
            stats[cat] = count
    return stats
