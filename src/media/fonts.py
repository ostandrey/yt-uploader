"""
Cross-platform font loading for Pillow overlays.

Railway/Linux has DejaVu (fonts-dejavu-core in Dockerfile), not Arial.
Pillow's load_default() bitmap font is latin-1 only and crashes on em dash (—).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# Prefer system fonts that support full Unicode (em dash, etc.).
_BOLD_CANDIDATES = (
    "arialbd.ttf",
    "Arial Bold.ttf",
    "arialblk.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)

_REGULAR_CANDIDATES = (
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)


@lru_cache(maxsize=32)
def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    # Last resort — may not render non-latin-1 glyphs.
    return ImageFont.load_default()


def ascii_safe(text: str) -> str:
    """Replace common Unicode punctuation that breaks latin-1 paths."""
    return (
        text.replace("\u2014", "-")  # em dash —
        .replace("\u2013", "-")  # en dash –
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
    )
