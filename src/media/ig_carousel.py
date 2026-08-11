"""Instagram 4:5 carousel — Glassdark What Moved. Operator does not design slides."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from src.content.naturalize import naturalize_text
from src.media.fonts import ascii_safe, load_font
from src.media.instagram_feed_image import pick_stock_keywords
from src.media.stock_image_fetcher import StockImageFetcher

W, H = 1080, 1350
SAFE = 80
TEXT_BOTTOM = H - 250
GOLD = (240, 180, 41)
BG = (8, 9, 14)
PANEL = (17, 19, 24)
TEXT = (229, 231, 235)
MUTED = (107, 114, 128)
YT = "@CryptoFinanceDigest"
TG = "t.me/coinwirenews"

_MONEY = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?\s?(?:billion|million|[BMKTbmkt])?|\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?(?:billion|million)\b)",
    re.I,
)


def _clip_words(text: str, n: int) -> str:
    words = naturalize_text(text).split()
    if len(words) <= n:
        return " ".join(words)
    return " ".join(words[:n])


def _sentences(text: str, max_n: int = 2) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", naturalize_text(text))
    return [s.strip() for s in raw if s.strip()][:max_n]


def _source_label(content: dict[str, Any]) -> str:
    link = str(content.get("source_link") or "")
    host = urlparse(link).netloc.replace("www.", "") if link else ""
    article = str(content.get("source_article") or "")
    if host:
        return host
    if article:
        return _clip_words(article, 6)
    return "primary source"


def build_what_moved(content: dict[str, Any]) -> list[dict[str, str]]:
    """Six slides. Never invent a number that is not in the article."""
    title = naturalize_text(content.get("title") or "Coin Wire")
    desc = naturalize_text(content.get("description") or "")
    script = naturalize_text(content.get("script") or "")
    blob = f"{title}. {desc}. {script}"
    money = _MONEY.search(blob)

    hook = _clip_words(title, 14)
    if money:
        fact_big = ascii_safe(money.group(1).strip())
        around = blob[max(0, money.start() - 40) : money.end() + 48]
        fact_sub = _clip_words(re.sub(re.escape(money.group(1)), "", around), 10) or "from the filing"
    else:
        fact_big = _clip_words(title, 8)
        fact_sub = "The number is in the story, not a forecast."

    context_bits = _sentences(desc, 2) or [
        ln for ln in script.splitlines() if ln and "follow coin wire" not in ln.lower()
    ][:2]
    context = " ".join(_clip_words(s, 16) for s in context_bits[:2]) or _clip_words(title, 16)

    return [
        {"kind": "hook", "rubric": "WHAT MOVED", "title": hook},
        {"kind": "fact", "rubric": "WHAT MOVED", "title": fact_big, "body": _clip_words(fact_sub, 12)},
        {"kind": "body", "rubric": "WHAT MOVED", "kicker": "Context", "title": context},
        {
            "kind": "body",
            "rubric": "WHAT MOVED",
            "kicker": "What to watch",
            "title": "Wait for the primary document. Don't trade the headline.",
        },
        {
            "kind": "body",
            "rubric": "WHAT MOVED",
            "kicker": "Source",
            "title": _source_label(content),
            "body": "What the outlet reported. We don't add numbers.",
        },
        {
            "kind": "cta",
            "rubric": "WHAT MOVED",
            "title": "Full story on YouTube",
            "body": YT,
            "meta": TG,
        },
    ]


def carousel_caption(content: dict[str, Any]) -> str:
    title = naturalize_text(content.get("title") or "")
    desc = _sentences(naturalize_text(content.get("description") or ""), 2)
    body = " ".join(desc) if desc else ""
    lines = [title]
    if body and body.lower() not in title.lower():
        lines.append(body)
    lines.append("")
    lines.append("Swipe for context. Full breakdown on YouTube.")
    lines.append("")
    lines.append("#bitcoin #crypto #cryptonews")
    return "\n".join(lines)[:2200]


def _blank(color: tuple[int, int, int] = BG) -> Image.Image:
    return Image.new("RGB", (W, H), color)


def _chrome(draw: ImageDraw.ImageDraw, rubric: str) -> None:
    brand = load_font(28, bold=True)
    meta = load_font(28, bold=True)
    draw.text((SAFE, SAFE), "COIN WIRE", fill=MUTED, font=brand)
    tag = (rubric or "").upper()
    box = draw.textbbox((0, 0), tag, font=meta)
    draw.text((W - SAFE - (box[2] - box[0]), SAFE), tag, fill=MUTED, font=meta)
    draw.rectangle((SAFE, 140, SAFE + 3, 320), fill=GOLD)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    text = ascii_safe(naturalize_text(text))
    if not text:
        return []
    lines: list[str] = []
    for para in textwrap.wrap(text, width=42):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            box = draw.textbbox((0, 0), trial, font=font)
            if box[2] - box[0] <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def _paint_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font,
    fill,
    gap: int = 10,
) -> int:
    for line in lines:
        if y > TEXT_BOTTOM - 40:
            break
        draw.text((x, y), line, fill=fill, font=font)
        box = draw.textbbox((0, 0), line, font=font)
        y += (box[3] - box[1]) + gap
    return y


def _darken(image: Image.Image, *, opacity: float = 0.65) -> Image.Image:
    shade = Image.new("RGB", image.size, BG)
    return Image.blend(image, shade, opacity)


def _stock_bg(title: str, keywords: Optional[list[str]], dest: Path) -> Optional[Image.Image]:
    fetcher = StockImageFetcher()
    if not fetcher.pexels_api_key and not fetcher.pixabay_api_key:
        return None
    meta = None
    for term in pick_stock_keywords(title, keywords) + [
        "stock exchange trading floor dark",
        "city skyline night",
    ]:
        meta = fetcher.fetch_image_for_keyword(term)
        if meta:
            break
    if not meta:
        return None
    raw = dest.with_suffix(".src.jpg")
    if not fetcher.download_image(meta, raw):
        return None
    try:
        image = Image.open(raw).convert("RGB")
        src_w, src_h = image.size
        ratio = W / H
        src_ratio = src_w / src_h
        if src_ratio > ratio:
            new_w = int(src_h * ratio)
            left = (src_w - new_w) // 2
            image = image.crop((left, 0, left + new_w, src_h))
        else:
            new_h = int(src_w / ratio)
            top = (src_h - new_h) // 2
            image = image.crop((0, top, src_w, top + new_h))
        image = image.resize((W, H), Image.Resampling.LANCZOS)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=3))
        image = _darken(image, opacity=0.62)
        overlay = Image.new("RGB", (W, H), BG)
        grad = Image.blend(image, overlay, 0.15)
        return grad
    finally:
        raw.unlink(missing_ok=True)


def _draw_slide(slide: dict[str, str], bg: Image.Image) -> Image.Image:
    image = bg.copy()
    draw = ImageDraw.Draw(image)
    _chrome(draw, slide.get("rubric") or "WHAT MOVED")
    x = SAFE + 30
    max_w = W - x - SAFE
    kind = slide.get("kind") or "body"
    title_font = load_font(64 if kind == "fact" else 52, bold=True)
    body_font = load_font(36, bold=False)
    kicker_font = load_font(32, bold=True)

    y = 360
    if slide.get("kicker"):
        y = _paint_lines(draw, [ascii_safe(slide["kicker"]).upper()], x=x, y=200, font=kicker_font, fill=GOLD)
        y += 24
    else:
        y = 200

    title_lines = _wrap(draw, slide.get("title") or "", title_font, max_w)
    y = _paint_lines(draw, title_lines, x=x, y=y, font=title_font, fill=TEXT, gap=12)
    if slide.get("body"):
        y += 18
        body_lines = _wrap(draw, slide["body"], body_font, max_w)
        y = _paint_lines(draw, body_lines, x=x, y=y, font=body_font, fill=MUTED, gap=8)
    if slide.get("meta"):
        _paint_lines(draw, [ascii_safe(slide["meta"])], x=x, y=min(y + 28, TEXT_BOTTOM - 50), font=body_font, fill=MUTED)
    return image


def render_what_moved(
    content: dict[str, Any],
    work_dir: Path,
    *,
    fetch_stock: bool = True,
) -> list[Path]:
    """Write 01.jpg…06.jpg + caption.txt. Stock only on slide 1."""
    out = Path(work_dir) / "ig_carousel"
    out.mkdir(parents=True, exist_ok=True)
    slides = build_what_moved(content)
    stock = None
    if fetch_stock:
        stock = _stock_bg(str(content.get("title") or ""), content.get("keywords") or [], out / "cover")
    paths: list[Path] = []
    for idx, slide in enumerate(slides, start=1):
        if idx == 1 and stock is not None:
            bg = stock
        elif slide.get("kind") == "hook":
            bg = _blank(BG)
        else:
            bg = _blank(PANEL)
        frame = _draw_slide(slide, bg)
        path = out / f"{idx:02d}.jpg"
        frame.save(path, format="JPEG", quality=92, optimize=True)
        paths.append(path)
    (out / "caption.txt").write_text(carousel_caption(content), encoding="utf-8")
    return paths
