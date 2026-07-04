"""
High-CTR thumbnails + channel branding assets for Coin Wire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.media.fonts import ascii_safe, load_font

BRAND = (0, 220, 150)
BRAND_DARK = (0, 160, 110)
RED = (255, 55, 55)
GREEN = (0, 230, 120)
YELLOW = (255, 220, 0)
BG_TOP = (4, 8, 18)
BG_BOTTOM = (10, 18, 32)

THUMB_W = 1280
THUMB_H = 720

BANNER_W = 2560
BANNER_H = 1440
PROFILE_SIZE = 800
WATERMARK_SIZE = 150


@dataclass
class ThumbHook:
    headline: str
    subline: str
    badge: Optional[str]
    accent: Tuple[int, int, int]
    direction: str  # up | down | neutral


def _measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text_lines(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int = 3,
) -> list[str]:
    """Wrap uppercase headline to fit within max_width pixels."""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    words = re.sub(r"\s+", " ", text.strip()).upper().split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        trial = " ".join(current + [word]) if current else word
        if _measure_text(draw, trial, font) <= max_width:
            current.append(word)
            continue
        if current:
            lines.append(" ".join(current))
            if len(lines) >= max_lines:
                return lines[:max_lines]
        current = [word]

    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines[:max_lines]


def _fit_headline_font(
    headline: str,
    max_width: int,
    max_lines: int = 3,
    start_size: int = 96,
    min_size: int = 56,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str]]:
    """Pick the largest font size where the headline fits in max_lines."""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    plain = headline.replace("\n", " ")

    for size in range(start_size, min_size - 1, -8):
        font = _font(size)
        lines = _wrap_text_lines(plain, font, max_width, max_lines=max_lines)
        if not lines:
            continue
        widest = max(_measure_text(draw, line, font) for line in lines)
        if widest <= max_width and len(lines) <= max_lines:
            return font, lines

    font = _font(min_size)
    return font, _wrap_text_lines(plain, font, max_width, max_lines=max_lines)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return load_font(size, bold=bold)


def _money_badge(text: str) -> Optional[str]:
    match = re.search(r"\$\s*([\d,.]+)\s*(million|billion|m|b)?", text, re.I)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    unit = (match.group(2) or "").lower()
    try:
        num = float(value)
    except ValueError:
        return None
    if unit in ("million", "m"):
        return f"${int(round(num))}M"
    if unit in ("billion", "b"):
        return f"${int(round(num))}B"
    if num >= 1_000_000:
        return f"${int(round(num / 1_000_000))}M"
    return f"${int(round(num))}"


def _percent_badge(text: str) -> Optional[str]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return f"{match.group(1)}%"
    match = re.search(r"(drop|fall|rise|surge|rally)", text, re.I)
    if match and "bitcoin" in text.lower():
        word = match.group(1).lower()
        if word in ("drop", "fall"):
            return "BTC ↓"
        return "BTC ↑"
    return None


def extract_thumb_hook(title: str) -> ThumbHook:
    lower = title.lower()

    if "etf" in lower and ("inflow" in lower or "outflow" in lower):
        badge = _money_badge(title) or "ETF"
        return ThumbHook(
            headline="ETF FLOWS\nSHIFT AGAIN",
            subline="Bitcoin funds on the move",
            badge=badge,
            accent=GREEN if "inflow" in lower else RED,
            direction="up" if "inflow" in lower else "down",
        )

    if "wall street" in lower or "wall st" in lower:
        return ThumbHook(
            headline="WALL ST.\n& CRYPTO",
            subline="Institutions shift focus",
            badge="NEWS",
            accent=BRAND,
            direction="neutral",
        )

    if "token" in lower:
        return ThumbHook(
            headline="TOKENIZATION\nWAVE BUILDS",
            subline="Wall St. mirrors crypto rails",
            badge="TOKEN",
            accent=BRAND,
            direction="up",
        )

    if "ethereum" in lower or " ether " in lower:
        return ThumbHook(
            headline="WALL ST.\nBETS ON ETH",
            subline="Institutions going deeper",
            badge="ETH",
            accent=GREEN,
            direction="up",
        )

    if "fed" in lower or "rate" in lower:
        return ThumbHook(
            headline="FED MOVE\nHITS CRYPTO",
            subline="Rates shake the market",
            badge="FED",
            accent=YELLOW,
            direction="neutral",
        )

    if "sec" in lower or "regulat" in lower:
        return ThumbHook(
            headline="SEC HEADLINE\nROCKS CRYPTO",
            subline="Regulation in focus",
            badge="SEC",
            accent=RED,
            direction="down",
        )

    if "bitcoin" in lower or "btc" in lower:
        badge = _percent_badge(title) or "BTC"
        down = any(w in lower for w in ("drop", "fall", "outflow", "decline", "sink"))
        return ThumbHook(
            headline="BITCOIN\nMAKES A MOVE",
            subline="Market reacts fast",
            badge=badge,
            accent=RED if down else GREEN,
            direction="down" if down else "up",
        )

    # Fallback: punchy first words, pre-wrapped
    words = re.sub(r"[^\w\s$%]", "", title).split()[:6]
    short = " ".join(words).upper()
    return ThumbHook(
        headline=short,
        subline="Breaking crypto news",
        badge="NEWS",
        accent=BRAND,
        direction="neutral",
    )


def _gradient_bg(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        blend = y / max(height - 1, 1)
        r = int(BG_TOP[0] * (1 - blend) + BG_BOTTOM[0] * blend)
        g = int(BG_TOP[1] * (1 - blend) + BG_BOTTOM[1] * blend)
        b = int(BG_TOP[2] * (1 - blend) + BG_BOTTOM[2] * blend)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return image


def _draw_glow_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: Tuple[int, int, int]) -> None:
    for step in range(r, 0, -8):
        alpha = int(40 * (step / r))
        c = tuple(min(255, ch + alpha) for ch in color)
        draw.ellipse([(cx - step, cy - step), (cx + step, cy + step)], fill=c)


def _draw_chart(draw: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int, bullish: bool) -> None:
    for x in range(x0, x0 + w, 40):
        draw.line([(x, y0), (x, y0 + h)], fill=(18, 28, 42), width=1)
    base = y0 + h - 50
    cx = x0 + 30
    for index, bar_h in enumerate([90, 150, 110, 200, 160, 230, 140, 210]):
        up = bullish if index % 2 == 0 else not bullish
        color = GREEN if up else RED
        draw.rectangle([(cx, base - bar_h), (cx + 24, base)], fill=color)
        cx += 34
    line_color = GREEN if bullish else RED
    draw.line([(x0 + 20, base - 40), (x0 + 200, base - 180), (x0 + w - 30, base - 260)], fill=line_color, width=6)


def _draw_badge(draw: ImageDraw.ImageDraw, text: str, cx: int, cy: int, color: Tuple[int, int, int], size: int = 120) -> None:
    _draw_glow_circle(draw, cx, cy, size, color)
    font = _font(int(size * 0.38))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 4), text, fill=(255, 255, 255), font=font)


def _draw_breaking_ribbon(draw: ImageDraw.ImageDraw) -> None:
    font = _font(28)
    draw.polygon([(36, 28), (260, 28), (240, 72), (36, 72)], fill=RED)
    draw.text((52, 34), "BREAKING", fill=(255, 255, 255), font=font)


def create_short_thumbnail(title: str, output_path: Path) -> Path:
    """1280x720 JPEG — click-optimized YouTube thumbnail."""
    hook = extract_thumb_hook(title)
    image = _gradient_bg(THUMB_W, THUMB_H)
    draw = ImageDraw.Draw(image)

    _draw_breaking_ribbon(draw)
    draw.rectangle([(0, THUMB_H - 5), (THUMB_W, THUMB_H)], fill=hook.accent)

    # Left column — headline block (~58% width)
    text_max_w = int(THUMB_W * 0.56)
    font_brand = _font(28)
    font_sub = _font(26, bold=False)

    draw.text((THUMB_W - 210, 36), "COIN WIRE", fill=BRAND, font=font_brand)

    font_head, headline_lines = _fit_headline_font(
        hook.headline,
        max_width=text_max_w,
        max_lines=3,
        start_size=68,
        min_size=44,
    )
    y = 96
    line_height = int(font_head.size * 1.08) if hasattr(font_head, "size") else 72
    for line in headline_lines:
        draw.text((53, y + 3), line, fill=(0, 0, 0), font=font_head)
        draw.text((50, y), line, fill=(255, 255, 255), font=font_head)
        y += line_height

    draw.text((50, y + 10), hook.subline, fill=(180, 195, 210), font=font_sub)

    # Right column — divider + badge + chart (no overlap)
    panel_x = int(THUMB_W * 0.60)
    draw.line([(panel_x, 50), (panel_x, THUMB_H - 30)], fill=(35, 50, 68), width=2)

    badge_cx = panel_x + (THUMB_W - panel_x) // 2
    if hook.badge:
        _draw_badge(draw, hook.badge, badge_cx, 200, hook.accent, size=100)

    chart_w = THUMB_W - panel_x - 50
    _draw_chart(
        draw,
        panel_x + 30,
        340,
        chart_w,
        THUMB_H - 380,
        bullish=hook.direction != "down",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=96, optimize=True)
    return output_path


def create_vertical_cover(title: str, output_path: Path) -> Path:
    """1080x1920 PNG — sharp hook frame for Short opener."""
    from src.media.chart_fallback import SHORT_HEIGHT, SHORT_WIDTH

    hook = extract_thumb_hook(title)
    image = _gradient_bg(SHORT_WIDTH, SHORT_HEIGHT)
    draw = ImageDraw.Draw(image)

    _draw_breaking_ribbon(draw)
    draw.rectangle([(0, 0), (SHORT_WIDTH, 8)], fill=hook.accent)

    font_brand = _font(44)
    font_sub = _font(36, bold=False)

    draw.text((70, 130), "COIN WIRE", fill=BRAND, font=font_brand)

    font_head, headline_lines = _fit_headline_font(
        hook.headline, max_width=SHORT_WIDTH - 140, max_lines=3
    )
    y = 360
    line_height = int(font_head.size * 1.05) if hasattr(font_head, "size") else 90
    for line in headline_lines:
        draw.text((73, y + 4), line, fill=(0, 0, 0), font=font_head)
        draw.text((70, y), line, fill=(255, 255, 255), font=font_head)
        y += line_height

    draw.text((70, y + 16), hook.subline, fill=(170, 185, 200), font=font_sub)

    if hook.badge:
        _draw_badge(draw, hook.badge, SHORT_WIDTH // 2, 1050, hook.accent, size=160)

    _draw_chart(draw, 100, 1250, 880, 520, bullish=hook.direction != "down")
    draw.text((70, 1820), "Tap to see the full story", fill=BRAND, font=_font(34, bold=False))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def create_channel_banner(output_path: Path, channel_name: str = "Coin Wire") -> Path:
    """2560x1440 — YouTube channel banner (safe zone centered)."""
    image = _gradient_bg(BANNER_W, BANNER_H)
    draw = ImageDraw.Draw(image)

    # Accent bands
    draw.rectangle([(0, 0), (BANNER_W, 12)], fill=BRAND)
    draw.rectangle([(0, BANNER_H - 12), (BANNER_W, BANNER_H)], fill=BRAND)

    _draw_chart(draw, 1800, 280, 620, 880, bullish=True)
    _draw_chart(draw, 140, 380, 620, 780, bullish=False)

    font_title = _font(120)
    font_sub = _font(48, bold=False)
    font_tag = _font(36, bold=False)

    title = channel_name.upper()
    draw.text((BANNER_W // 2 - 420, 520), title, fill=(255, 255, 255), font=font_title)
    draw.text((BANNER_W // 2 - 380, 660), "CRYPTO MARKET NEWS IN 60 SECONDS", fill=BRAND, font=font_sub)
    draw.text((BANNER_W // 2 - 260, 740), "Daily Shorts  •  @coinwirenews", fill=(150, 165, 185), font=font_tag)

    # Center safe highlight box (TV safe area guide)
    draw.rounded_rectangle(
        [(BANNER_W // 2 - 420, 480), (BANNER_W // 2 + 420, 820)],
        radius=24,
        outline=(*BRAND, 80),
        width=2,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def create_channel_profile(output_path: Path) -> Path:
    """800x800 — channel profile picture."""
    image = Image.new("RGB", (PROFILE_SIZE, PROFILE_SIZE), BG_TOP)
    draw = ImageDraw.Draw(image)

    cx, cy = PROFILE_SIZE // 2, PROFILE_SIZE // 2
    _draw_glow_circle(draw, cx, cy, 360, BRAND_DARK)
    draw.ellipse([(80, 80), (PROFILE_SIZE - 80, PROFILE_SIZE - 80)], outline=BRAND, width=12)

    font = _font(72)
    font_sm = _font(28, bold=False)
    lines = ["COIN", "WIRE"]
    y = cy - 80
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y), line, fill=(255, 255, 255), font=font)
        y += 76

    sub = "CRYPTO NEWS"
    bbox = draw.textbbox((0, 0), sub, font=font_sm)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, cy + 90), sub, fill=BRAND, font=font_sm)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def create_video_watermark(output_path: Path) -> Path:
    """150x150 — subtle corner watermark for all videos."""
    image = Image.new("RGBA", (WATERMARK_SIZE, WATERMARK_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([(8, 8), (142, 142)], radius=16, fill=(8, 12, 22, 200), outline=(*BRAND, 255), width=3)
    font = _font(22)
    draw.text((22, 48), "COIN", fill=(255, 255, 255, 255), font=font)
    draw.text((22, 72), "WIRE", fill=(*BRAND, 255), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path
