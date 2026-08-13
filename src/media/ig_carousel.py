"""Instagram 4:5 carousel — four type-only What Moved slides."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw

from src.content.naturalize import naturalize_text
from src.media.fonts import ascii_safe, load_font

W, H = 1080, 1350
SAFE = 80
TEXT_BOTTOM = H - 220
GOLD = (240, 180, 41)
BG = (8, 9, 14)
TEXT = (229, 231, 235)
MUTED = (107, 114, 128)
RULE = (30, 32, 40)
HANDLE = "@coinwirenews"

_MONEY_CORE = (
    r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:billion|million|trillion|[BMKTbmkt])?"
    r"|\d+(?:\.\d+)?\s?%"
    r"|\d+(?:\.\d+)?\s?(?:billion|million|trillion)\b"
)
_MONEY = re.compile(rf"({_MONEY_CORE})", re.I)
_MONEY_WITH_PREP = re.compile(
    rf"(?:\b(?:for|at|of|worth|valued(?:\s+at)?)\s+)?(?:{_MONEY_CORE})",
    re.I,
)
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_JUNK_LINE = re.compile(
    r"^(source|read more|follow|full story|subscribe|swipe|http)\b",
    re.I,
)
_STOP = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _clip_words(text: str, n: int) -> str:
    words = naturalize_text(text).split()
    if len(words) <= n:
        return " ".join(words)
    return " ".join(words[:n])


def _scrub(text: str) -> str:
    raw = _URL.sub(" ", naturalize_text(text or ""))
    raw = re.sub(r"\b(?:Read more|Source|Follow)\s*:?\s*", " ", raw, flags=re.I)
    return re.sub(r"\s+", " ", raw).strip(" .,-")


def _sentences(text: str, max_n: int = 8) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", naturalize_text(text or ""))
    out: list[str] = []
    for sent in raw:
        if _JUNK_LINE.match(sent.strip()):
            continue
        sent = _scrub(sent)
        if not sent or _JUNK_LINE.match(sent):
            continue
        if "@" in sent or re.search(r"\bfollow\b", sent, re.I):
            continue
        if len(sent.split()) < 5:
            continue
        out.append(sent)
        if len(out) >= max_n:
            break
    return out


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$]+", text.lower()) if w not in _STOP}


def _distinct_from(text: str, other: str) -> bool:
    a, b = _tokens(text), _tokens(other)
    if not a or not b:
        return True
    return len(a & b) / len(a) < 0.65


def _source_label(content: dict[str, Any]) -> str:
    link = str(content.get("source_link") or "")
    host = urlparse(link).netloc.replace("www.", "") if link else ""
    if host:
        return host
    article = _scrub(str(content.get("source_article") or ""))
    if article:
        return _clip_words(article, 4)
    return ""


def _fact_sub(title: str, desc: str, money: re.Match[str]) -> str:
    leftover = _MONEY_WITH_PREP.sub(" ", title)
    leftover = re.sub(r"\s+", " ", leftover).strip(" .,-")
    leftover = re.sub(r"\bfor\s+in\b", "in", leftover, flags=re.I)
    leftover = re.sub(r"\s+in\s+(ETFs?|crypto|bitcoin|ether(?:eum)?)\s*$", "", leftover, flags=re.I)
    leftover = _clip_words(leftover, 14)
    if leftover and _distinct_from(leftover, money.group(1)):
        return leftover
    for sent in _sentences(desc, 3):
        if money.group(1).lower() not in sent.lower() and _distinct_from(sent, title):
            return _clip_words(sent, 14)
    return "The figure reported in the story."


def _context_copy(desc: str, script: str, title: str) -> str:
    parts: list[str] = []
    for src in (desc, script):
        for sent in _sentences(src, 8):
            if not _distinct_from(sent, title):
                continue
            if any(not _distinct_from(sent, prev) for prev in parts):
                continue
            clipped = _clip_words(sent, 16).rstrip(".")
            if not clipped:
                continue
            parts.append(clipped)
            if len(parts) >= 2:
                return ". ".join(parts) + "."
    if parts:
        return parts[0].rstrip(".") + "."
    return "The outlet published the details. We don't add numbers."


def build_what_moved(content: dict[str, Any]) -> list[dict[str, str]]:
    """Four slides. Never invent a number that is not in the article."""
    title = naturalize_text(content.get("title") or "Coin Wire")
    desc = naturalize_text(content.get("description") or "")
    script = naturalize_text(content.get("script") or "")
    blob = f"{title}. {desc}. {script}"
    money = _MONEY.search(blob)
    source = _source_label(content)

    hook = _clip_words(_scrub(title), 16)
    if money:
        fact_big = ascii_safe(money.group(1).strip())
        fact_sub = _fact_sub(title, desc, money)
    else:
        fact_big = _clip_words(_scrub(title), 8)
        fact_sub = "The number is in the story, not a forecast."

    context = _context_copy(desc, script, title)
    last: dict[str, str] = {
        "kind": "watch",
        "rubric": "WHAT MOVED",
        "kicker": "What to watch",
        "title": "Wait for the primary document. Don't trade the headline.",
        "body": f"Follow {HANDLE} for daily crypto market moves.",
    }
    if source:
        last["meta"] = f"Source: {source}"

    return [
        {"kind": "hook", "rubric": "WHAT MOVED", "title": hook},
        {"kind": "fact", "rubric": "WHAT MOVED", "title": fact_big, "body": fact_sub},
        {"kind": "body", "rubric": "WHAT MOVED", "kicker": "Context", "title": context},
        last,
    ]


def carousel_caption(content: dict[str, Any]) -> str:
    override = naturalize_text(str(content.get("carousel_caption") or "")).strip()
    if override:
        return _URL.sub("", override).strip()[:2200]
    title = _scrub(content.get("title") or "")
    desc = _sentences(content.get("description") or "", 2)
    body = " ".join(desc) if desc else ""
    source = _source_label(content)
    lines = [title]
    if body and body.lower() not in title.lower() and _distinct_from(body, title):
        lines.append(body)
    lines.append("Swipe for context.")
    if source:
        lines.append(f"Source: {source}")
    lines.append("#bitcoin #crypto #cryptonews #etf")
    return "\n".join(lines)[:2200]


def _blank() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def _chrome(draw: ImageDraw.ImageDraw, rubric: str) -> None:
    brand = load_font(26, bold=True)
    meta = load_font(26, bold=True)
    draw.text((SAFE, 72), "COIN WIRE", fill=MUTED, font=brand)
    tag = (rubric or "WHAT MOVED").upper()
    box = draw.textbbox((0, 0), tag, font=meta)
    draw.text((W - SAFE - (box[2] - box[0]), 72), tag, fill=MUTED, font=meta)
    draw.rectangle((SAFE, 128, W - SAFE, 131), fill=RULE)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    text = ascii_safe(naturalize_text(text))
    if not text:
        return []
    lines: list[str] = []
    cur = ""
    for word in text.split():
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
    gap: int = 12,
) -> int:
    for line in lines:
        if y > TEXT_BOTTOM - 40:
            break
        draw.text((x, y), line, fill=fill, font=font)
        box = draw.textbbox((0, 0), line, font=font)
        y += (box[3] - box[1]) + gap
    return y


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_w: int,
    start: int,
    min_size: int,
    max_lines: int,
    bold: bool = True,
) -> tuple[Any, list[str]]:
    for size in range(start, min_size - 1, -2):
        font = load_font(size, bold=bold)
        lines = _wrap(draw, text, font, max_w)
        if len(lines) <= max_lines:
            return font, lines
    font = load_font(min_size, bold=bold)
    return font, _wrap(draw, text, font, max_w)[:max_lines]


def _draw_content(draw: ImageDraw.ImageDraw, slide: dict[str, str], y: int) -> int:
    kind = slide.get("kind") or "body"
    tick_x = SAFE
    x = SAFE + 28
    max_w = W - x - SAFE
    kicker_font = load_font(30, bold=True)
    body_font = load_font(36, bold=False)

    if slide.get("kicker"):
        kicker = ascii_safe(slide["kicker"]).upper()
        draw.rectangle((tick_x, y + 6, tick_x + 4, y + 34), fill=GOLD)
        y = _paint_lines(draw, [kicker], x=x, y=y, font=kicker_font, fill=GOLD, gap=8)
        y += 28
    else:
        draw.rectangle((tick_x, y + 10, tick_x + 4, y + 86), fill=GOLD)

    if kind == "fact":
        title_font, title_lines = _fit_lines(
            draw, slide.get("title") or "", max_w=max_w, start=96, min_size=56, max_lines=2
        )
        y = _paint_lines(draw, title_lines, x=x, y=y, font=title_font, fill=TEXT, gap=10)
    elif kind == "hook":
        title_font, title_lines = _fit_lines(
            draw, slide.get("title") or "", max_w=max_w, start=64, min_size=42, max_lines=5
        )
        y = _paint_lines(draw, title_lines, x=x, y=y, font=title_font, fill=TEXT, gap=18)
    else:
        title_font, title_lines = _fit_lines(
            draw, slide.get("title") or "", max_w=max_w, start=48, min_size=36, max_lines=7, bold=True
        )
        y = _paint_lines(draw, title_lines, x=x, y=y, font=title_font, fill=TEXT, gap=16)

    if slide.get("body"):
        y += 32
        body_lines = _wrap(draw, slide["body"], body_font, max_w)
        y = _paint_lines(draw, body_lines, x=x, y=y, font=body_font, fill=MUTED, gap=12)
    return y


def _draw_slide(slide: dict[str, str], bg: Image.Image) -> Image.Image:
    image = bg.copy()
    draw = ImageDraw.Draw(image)
    _chrome(draw, slide.get("rubric") or "WHAT MOVED")
    scratch = Image.new("RGB", (W, H), BG)
    height = _draw_content(ImageDraw.Draw(scratch), slide, 0)
    available = TEXT_BOTTOM - 168
    top_pad = max(20, min(220, (available - height) // 3))
    y = min(168 + top_pad, max(168, TEXT_BOTTOM - height - 8))
    _draw_content(draw, slide, y)
    if slide.get("meta"):
        meta_font = load_font(26, bold=False)
        _paint_lines(
            draw,
            [ascii_safe(slide["meta"])],
            x=SAFE + 28,
            y=TEXT_BOTTOM - 20,
            font=meta_font,
            fill=MUTED,
            gap=6,
        )
    return image


def render_what_moved(
    content: dict[str, Any],
    work_dir: Path,
    *,
    fetch_stock: bool = True,
) -> list[Path]:
    """Write 01.jpg…04.jpg + caption.txt. Type-only; fetch_stock is ignored."""
    del fetch_stock
    out = Path(work_dir) / "ig_carousel"
    out.mkdir(parents=True, exist_ok=True)
    slides = build_what_moved(content)
    paths: list[Path] = []
    for idx, slide in enumerate(slides, start=1):
        frame = _draw_slide(slide, _blank())
        path = out / f"{idx:02d}.jpg"
        frame.save(path, format="JPEG", quality=92, optimize=True)
        paths.append(path)
    (out / "caption.txt").write_text(carousel_caption(content), encoding="utf-8")
    return paths
