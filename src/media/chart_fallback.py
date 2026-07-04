"""
Branded chart-card B-roll — native 1080x1920, always sharp (no stock upscale).
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from src.media.fonts import ascii_safe, load_font
from src.media.video_encode import INTERMEDIATE_ENCODE_ARGS

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
RENDER_SCALE = 2  # supersample 2x then downscale for crisp text/lines
BRAND = (0, 220, 150)


def _font(size: int, bold: bool = True):
    return load_font(size, bold=bold)


def create_chart_card_png(label: str, output_path: Path) -> Path:
    """News-style chart graphic at 2x resolution for supersampled downscale."""
    w, h = SHORT_WIDTH * RENDER_SCALE, SHORT_HEIGHT * RENDER_SCALE
    image = Image.new("RGB", (w, h), (8, 12, 22))
    draw = ImageDraw.Draw(image)
    scale = RENDER_SCALE

    for x in range(0, w, 80 * scale):
        draw.line([(x, 200 * scale), (x, 1500 * scale)], fill=(20, 28, 42), width=scale)
    for y in range(200 * scale, 1500 * scale, 80 * scale):
        draw.line([(60 * scale, y), (w - 60 * scale, y)], fill=(20, 28, 42), width=scale)

    random.seed(label)
    x = 120 * scale
    base = 900 * scale
    for _ in range(14):
        bar_h = random.randint(80, 280) * scale
        bullish = random.random() > 0.45
        color = (0, 200, 120) if bullish else (220, 60, 60)
        draw.rectangle(
            [(x, base - bar_h), (x + 36 * scale, base)],
            fill=color,
        )
        x += 58 * scale

    draw.line(
        [
            (100 * scale, 1100 * scale),
            (400 * scale, 750 * scale),
            (700 * scale, 820 * scale),
            (980 * scale, 500 * scale),
        ],
        fill=BRAND,
        width=4 * scale,
    )

    draw.text((70 * scale, 100 * scale), "COIN WIRE", fill=BRAND, font=_font(42 * scale))
    draw.text(
        (70 * scale, 1550 * scale),
        ascii_safe(label).upper()[:40],
        fill=(230, 235, 245),
        font=_font(28 * scale, bold=False),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, optimize=True)
    return output_path


def create_chart_card_video(
    label: str,
    output_path: Path,
    duration_sec: float,
    fps: int = 30,
) -> Path:
    png = output_path.with_suffix(".png")
    create_chart_card_png(label, png)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg, "-y", "-loop", "1", "-i", str(png),
            "-t", str(duration_sec),
            "-vf",
            f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:flags=lanczos,format=yuv420p",
            "-r", str(fps), "-an",
            *INTERMEDIATE_ENCODE_ARGS,
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
