"""
Local B-roll clip library — zero API latency, used before Pexels/Pixabay.

Drop portrait MP4s into:
  data/assets/broll_library/{category}/*.mp4

Clips with reject:true in *.meta.json (or under _rejected/) are skipped.
Fill via: python scripts/fill_broll_library.py

Categories: bitcoin, ethereum, macro, regulation, security, defi, default
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional, Set

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIBRARY = ROOT / "data" / "assets" / "broll_library"


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


def pick_local_clip(
    category: str,
    used_paths: Set[str],
    library_root: Optional[Path] = None,
) -> Optional[Path]:
    """Return a random unused local clip for category, or None."""
    clips = list_library_clips(library_root or DEFAULT_LIBRARY, category)
    if not clips:
        return None

    unused = [c for c in clips if str(c.resolve()) not in used_paths]
    pool = unused or clips
    return random.choice(pool)


def library_stats(library_root: Optional[Path] = None) -> dict[str, int]:
    root = library_root or DEFAULT_LIBRARY
    stats: dict[str, int] = {}
    for cat in VALID_CATEGORIES:
        count = len(list_library_clips(root, cat)) if (root / cat).is_dir() else 0
        if count:
            stats[cat] = count
    return stats
