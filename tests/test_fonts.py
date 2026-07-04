"""Font loading and unicode-safe overlay text."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from src.media.fonts import ascii_safe, load_font
from src.media.script_parser import extract_outro_summary
from src.media.text_overlay import create_outro_png


def test_ascii_safe_replaces_em_dash():
    assert "\u2014" not in ascii_safe("Crypto moves fast — follow")
    assert ascii_safe("Crypto moves fast — follow") == "Crypto moves fast - follow"


def test_load_font_returns_usable_font():
    font = load_font(32, bold=True)
    image = Image.new("RGB", (200, 80), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Must not raise latin-1 UnicodeEncodeError on em dash.
    draw.text((10, 10), "BTC — live", fill=(255, 255, 255), font=font)


def test_outro_png_handles_em_dash(tmp_path: Path):
    out = tmp_path / "outro.png"
    create_outro_png(out, summary="Crypto moves fast — follow for daily updates.")
    assert out.exists()
    assert out.stat().st_size > 1000


def test_outro_summary_is_ascii_safe():
    summary = extract_outro_summary("Bitcoin and crypto markets moved today.")
    summary.encode("latin-1")  # must not raise
