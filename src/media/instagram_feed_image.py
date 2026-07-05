"""
Instagram feed image: stock photo + headline overlay.

Uses Pexels/Pixabay (same keys as Shorts B-roll). Falls back to local
thumbnail only when stock APIs are unavailable.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from src.content.naturalize import naturalize_text
from src.media.fonts import load_font
from src.media.stock_image_fetcher import StockImageFetcher

FEED_W = 1080
FEED_H = 1350
BRAND = (0, 255, 136)

_STOCK_KEYWORDS = (
    "bitcoin",
    "ethereum",
    "fed",
    "federal reserve",
    "sec",
    "etf",
    "defi",
    "regulation",
    "crypto",
    "blockchain",
    "trading",
    "wall street",
)


def pick_stock_keywords(title: str, keywords: Optional[List[str]] = None) -> List[str]:
    """Return 1-2 search terms for stock photos, most specific first."""
    lower = naturalize_text(title).lower()
    found: List[str] = []
    for token in _STOCK_KEYWORDS:
        if token in lower and token not in found:
            found.append(token)
    if keywords:
        for kw in keywords:
            clean = naturalize_text(kw).lower().strip()
            if len(clean) >= 3 and clean not in found:
                found.append(clean)
    if not found:
        found.append("cryptocurrency news")
    if len(found) == 1:
        found.append("bitcoin trading chart")
    return found[:2]


def _fit_headline_font(
    draw: ImageDraw.ImageDraw,
    headline: str,
    max_width: int,
    *,
    max_lines: int = 4,
    start_size: int = 56,
    min_size: int = 34,
):
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size, bold=True)
        lines = textwrap.wrap(headline, width=max(12, int(max_width / (size * 0.52))))
        lines = lines[:max_lines]
        if not lines:
            continue
        heights = []
        widths = []
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font)
            widths.append(box[2] - box[0])
            heights.append(box[3] - box[1])
        if max(widths) <= max_width and sum(heights) + (len(lines) - 1) * 8 <= 360:
            return font, lines
    font = load_font(min_size, bold=True)
    lines = textwrap.wrap(headline, width=24)[:max_lines]
    return font, lines


def _prepare_background(source: Path) -> Image.Image:
    image = Image.open(source).convert("RGB")
    src_w, src_h = image.size
    target_ratio = FEED_W / FEED_H
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        image = image.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        image = image.crop((0, top, src_w, top + new_h))

    image = image.resize((FEED_W, FEED_H), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=3))
    return image


def _draw_headline_overlay(image: Image.Image, headline: str) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    grad_top = int(FEED_H * 0.55)
    for y in range(grad_top, FEED_H):
        t = (y - grad_top) / max(FEED_H - grad_top, 1)
        alpha = int(210 * (t**1.4))
        draw.line([(0, y), (FEED_W, y)], fill=(0, 0, 0, alpha))

    brand_font = load_font(28, bold=True)
    draw.text((48, 42), "COIN WIRE", fill=(*BRAND, 255), font=brand_font)

    headline = naturalize_text(headline)
    text_draw = ImageDraw.Draw(base)
    text_max_w = FEED_W - 96
    font, lines = _fit_headline_font(text_draw, headline, text_max_w)
    y = FEED_H - 48
    for line in reversed(lines):
        box = text_draw.textbbox((0, 0), line, font=font)
        line_h = box[3] - box[1]
        y -= line_h
        draw.text((51, y + 3), line, fill=(0, 0, 0, 220), font=font)
        draw.text((48, y), line, fill=(255, 255, 255, 255), font=font)
        y -= 10

    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def create_feed_image_from_stock(
    title: str,
    output_path: Path,
    *,
    keywords: Optional[List[str]] = None,
    with_headline: bool = True,
) -> Optional[Path]:
    """Download a portrait stock photo and optionally overlay the headline."""
    fetcher = StockImageFetcher()
    if not fetcher.pexels_api_key and not fetcher.pixabay_api_key:
        return None

    search_terms = pick_stock_keywords(title, keywords)
    image_meta = None
    for term in search_terms:
        image_meta = fetcher.fetch_image_for_keyword(term)
        if image_meta:
            break
    if not image_meta:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = output_path.with_suffix(".src.jpg")
    if not fetcher.download_image(image_meta, raw_path):
        return None

    try:
        prepared = _prepare_background(raw_path)
        if with_headline:
            prepared = _draw_headline_overlay(prepared, title)
        prepared.save(output_path, format="JPEG", quality=92, optimize=True)
        return output_path
    finally:
        raw_path.unlink(missing_ok=True)


def create_instagram_feed_assets(
    title: str,
    work_dir: Path,
    *,
    keywords: Optional[List[str]] = None,
    carousel: bool = False,
    thumbnail_fallback: Optional[Path] = None,
) -> List[Path]:
    """
    Build 1 (feed) or 2 (carousel) JPEGs for Instagram feed posts.
    First slide always has the headline; second slide is stock-only.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    primary = work_dir / "ig_feed_primary.jpg"
    if create_feed_image_from_stock(title, primary, keywords=keywords, with_headline=True):
        paths.append(primary)
    elif thumbnail_fallback and thumbnail_fallback.exists():
        paths.append(thumbnail_fallback)

    if not paths:
        return []

    if carousel:
        secondary = work_dir / "ig_feed_secondary.jpg"
        fetcher = StockImageFetcher()
        terms = pick_stock_keywords(title, keywords)
        second_term = terms[-1] if len(terms) > 1 else "crypto market chart"
        image_meta = fetcher.fetch_image_for_keyword(second_term)
        if image_meta and fetcher.download_image(image_meta, secondary.with_suffix(".src.jpg")):
            try:
                prepared = _prepare_background(secondary.with_suffix(".src.jpg"))
                prepared.save(secondary, format="JPEG", quality=92, optimize=True)
                paths.append(secondary)
            finally:
                secondary.with_suffix(".src.jpg").unlink(missing_ok=True)

    return paths
