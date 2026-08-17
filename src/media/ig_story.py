"""Instagram Stories 9:16 — pad carousel slide 1, optional quote-card."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from src.content.naturalize import naturalize_text
from src.media.fonts import ascii_safe, load_font
from src.paths import coin_wire_storage

STORY_W, STORY_H = 1080, 1920
BG = (8, 9, 14)
GOLD = (240, 180, 41)
TEXT = (229, 231, 235)
MUTED = (107, 114, 128)
HANDLE = "@coinwirenews"

_MONEY = re.compile(r"\$|\d+(?:\.\d+)?\s?%")
_REGULATORY = re.compile(r"\b(SEC|CFTC|Fed|FOMC|OCC|committee|filing|rule)\b", re.I)
_FLOW = re.compile(r"\b(ETF|inflow|outflow|flow|BlackRock|Fidelity)\b", re.I)
_MACRO = re.compile(r"\b(Fed|FOMC|rates|CPI|inflation|Treasury|jobs)\b", re.I)

THEME_QUERIES = {
    "regulatory": "dark navy abstract architecture",
    "flow": "dark abstract gold light finance",
    "macro": "dark navy city lights abstract",
    "generic": "dark abstract navy yellow light",
}


def story_dir() -> Path:
    return coin_wire_storage() / "ig_story"


def story_bg_dir() -> Path:
    return coin_wire_storage() / "ig_story_bg"


def _clip_words(text: str, n: int) -> str:
    words = naturalize_text(text).split()
    if len(words) <= n:
        return " ".join(words)
    return " ".join(words[:n])


def pick_theme(blob: str) -> str:
    if _REGULATORY.search(blob) and not _FLOW.search(blob):
        return "regulatory"
    if _FLOW.search(blob):
        return "flow"
    if _MACRO.search(blob):
        return "macro"
    return "generic"


def _cover_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    if src_w < 1 or src_h < 1:
        return Image.new("RGB", (width, height), BG)
    target_ratio = width / height
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        image = image.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        image = image.crop((0, top, src_w, top + new_h))
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    return ImageEnhance.Contrast(image).enhance(1.06).filter(
        ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=3)
    )


def ensure_story_backgrounds(*, max_age_days: int = 7) -> dict[str, Path]:
    """Fetch four themed stock stills once a week. Missing themes are skipped."""
    out: dict[str, Path] = {}
    folder = story_bg_dir()
    folder.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    from src.media.stock_image_fetcher import StockImageFetcher

    fetcher = StockImageFetcher()
    if not fetcher.pexels_api_key and not fetcher.pixabay_api_key:
        return out
    for theme, query in THEME_QUERIES.items():
        path = folder / f"{theme}.jpg"
        if path.is_file():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if mtime >= cutoff:
                out[theme] = path
                continue
        meta = fetcher.fetch_image_for_keyword(query)
        if not meta:
            if path.is_file():
                out[theme] = path
            continue
        raw = path.with_suffix(".src.jpg")
        if not fetcher.download_image(meta, raw):
            if path.is_file():
                out[theme] = path
            continue
        try:
            image = Image.open(raw).convert("RGB")
            _cover_resize(image, STORY_W, STORY_H).save(
                path, format="JPEG", quality=90, optimize=True
            )
            out[theme] = path
        except OSError:
            if path.is_file():
                out[theme] = path
        finally:
            if raw.is_file():
                raw.unlink(missing_ok=True)
    return out


def render_padded_story(slide_path: Path, dest: Path) -> Path:
    slide = Image.open(slide_path).convert("RGB")
    if slide.width != STORY_W:
        ratio = STORY_W / slide.width
        slide = slide.resize((STORY_W, int(slide.height * ratio)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (STORY_W, STORY_H), BG)
    y = max(0, (STORY_H - slide.height) // 2)
    canvas.paste(slide, (0, y))
    draw = ImageDraw.Draw(canvas)
    font = load_font(28, bold=False)
    label = "Link in bio"
    box = draw.textbbox((0, 0), label, font=font)
    tw = box[2] - box[0]
    draw.text(((STORY_W - tw) // 2, STORY_H - 120), label, fill=MUTED, font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, format="JPEG", quality=92, optimize=True)
    return dest


def render_quote_card(takeaway: str, dest: Path, *, theme: str = "generic") -> Optional[Path]:
    backgrounds = ensure_story_backgrounds()
    bg_path = (
        backgrounds.get(theme)
        or backgrounds.get("generic")
        or next(iter(backgrounds.values()), None)
    )
    if not bg_path:
        return None
    line = ascii_safe(_clip_words(takeaway, 12))
    if not line:
        return None
    image = Image.open(bg_path).convert("RGB")
    if image.size != (STORY_W, STORY_H):
        image = _cover_resize(image, STORY_W, STORY_H)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(STORY_H):
        t = abs(y - STORY_H / 2) / (STORY_H / 2)
        alpha = int(90 + 90 * (1 - min(t, 1)))
        draw.line([(0, y), (STORY_W, y)], fill=(8, 9, 14, alpha))
    base = image.convert("RGBA")
    combined = Image.alpha_composite(base, overlay).convert("RGB")
    ink = ImageDraw.Draw(combined)
    brand = load_font(28, bold=True)
    ink.text((80, 140), "COIN WIRE", fill=GOLD, font=brand)
    body_font = load_font(52, bold=True)
    words = line.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        box = ink.textbbox((0, 0), trial, font=body_font)
        if box[2] - box[0] <= STORY_W - 160:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    y = STORY_H // 2 - 40 * len(lines)
    for row in lines:
        box = ink.textbbox((0, 0), row, font=body_font)
        tw = box[2] - box[0]
        ink.text(((STORY_W - tw) // 2, y), row, fill=TEXT, font=body_font)
        y += (box[3] - box[1]) + 16
    footer = load_font(28, bold=False)
    foot = f"Full story: {HANDLE}"
    box = ink.textbbox((0, 0), foot, font=footer)
    ink.text(((STORY_W - (box[2] - box[0])) // 2, STORY_H - 220), foot, fill=MUTED, font=footer)
    bio = "Link in bio"
    box = ink.textbbox((0, 0), bio, font=footer)
    ink.text(((STORY_W - (box[2] - box[0])) // 2, STORY_H - 120), bio, fill=MUTED, font=footer)
    dest.parent.mkdir(parents=True, exist_ok=True)
    combined.save(dest, format="JPEG", quality=92, optimize=True)
    return dest


def _quote_card_wanted(takeaway: str, content: dict[str, Any]) -> bool:
    if content.get("allow_quote_card") is False:
        return False
    if not _MONEY.search(takeaway or ""):
        return False
    try:
        from src.content.editorial_jobs import _editorial_cfg, _load_state, _tz
    except Exception:
        return False
    try:
        import yaml

        root = Path(__file__).resolve().parents[2]
        loaded = yaml.safe_load((root / "config" / "coin_wire.yaml").read_text(encoding="utf-8"))
        config = loaded if isinstance(loaded, dict) else {}
    except Exception:
        config = {}
    tz_name = _tz(config) if config else "America/New_York"
    cap = int(_editorial_cfg(config).get("story_quote_per_week", 3) or 3)
    state = _load_state(tz_name)
    return int(state.get("story_quote", 0)) < cap


def _record_quote_card() -> None:
    try:
        import yaml

        from src.content.editorial_jobs import _editorial_cfg, _load_state, _save_state, _tz

        root = Path(__file__).resolve().parents[2]
        config = yaml.safe_load((root / "config" / "coin_wire.yaml").read_text(encoding="utf-8"))
        tz_name = _tz(config) if config else "America/New_York"
        state = _load_state(tz_name)
        state["story_quote"] = int(state.get("story_quote", 0)) + 1
        _save_state(state)
    except Exception:
        pass


def render_ig_story(slide_path: Path, dest: Path, content: Optional[dict[str, Any]] = None) -> Path:
    content = content or {}
    takeaway = naturalize_text(str(content.get("takeaway") or "")).strip()
    blob = f"{content.get('title') or ''} {content.get('description') or ''} {takeaway}"
    if takeaway and _quote_card_wanted(takeaway, content):
        theme = pick_theme(blob)
        try:
            quoted = render_quote_card(takeaway, dest, theme=theme)
        except Exception:
            quoted = None
        if quoted:
            _record_quote_card()
            return quoted
    return render_padded_story(slide_path, dest)
