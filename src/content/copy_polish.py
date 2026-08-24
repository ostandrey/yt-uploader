"""Post-process LLM copy: hashtags, CTA, anti-AI cleanup."""

from __future__ import annotations

import re

from src.content.naturalize import naturalize_text
from src.content.voice import SHORT_SCRIPT_CTA, copy_contains_banned
from src.publishers.captions import (
    CAROUSEL_CTA,
    IG_CTA,
    fix_hashtag_block,
    pick_ig_hashtag_tags,
)

_RE_HASHTAG_LINE = re.compile(r"^#\w+", re.MULTILINE)


def _strip_hashtag_lines(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def polish_ig_caption(caption: str, article_text: str) -> str:
    body = _strip_hashtag_lines(naturalize_text(caption))
    if IG_CTA not in body and "Full breakdown" not in body:
        body = f"{body}\n\n{IG_CTA}".strip()
    tags = " ".join(f"#{t}" for t in pick_ig_hashtag_tags(article_text, 5))
    return f"{body}\n\n{tags}".strip()


def polish_carousel_caption(
    caption: str,
    article_text: str,
    *,
    source: str = "",
    context_slide: str = "",
) -> str:
    from src.content.copy_overlap import shares_lead

    body = _strip_hashtag_lines(naturalize_text(caption))
    if context_slide and shares_lead(body, [context_slide], threshold=0.55):
        # Keep hook line only — CONTEXT lives on the slide, not in the caption.
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        body = first
    if CAROUSEL_CTA not in body:
        body = f"{body}\n\n{CAROUSEL_CTA}".strip()
    if source and "Source:" not in body:
        body = f"{body}\n\nSource: {source}".strip()
    tags = " ".join(f"#{t}" for t in pick_ig_hashtag_tags(article_text, 4))
    return f"{body}\n\n{tags}".strip()


def polish_script_lines(lines: list[str]) -> str:
    cleaned = [naturalize_text(str(line).strip()) for line in lines if str(line).strip()]
    if not cleaned:
        return ""
    if cleaned[-1].lower() != SHORT_SCRIPT_CTA.lower():
        if "follow coin wire" not in cleaned[-1].lower():
            cleaned.append(SHORT_SCRIPT_CTA)
        else:
            cleaned[-1] = SHORT_SCRIPT_CTA
    return "\n".join(cleaned[:5])


def llm_copy_passes_qa(text: str) -> bool:
    if copy_contains_banned(text):
        return False
    for sentence in re.split(r"[.!?]\s+", text):
        words = sentence.split()
        if len(words) > 20:
            return False
    return True


def polish_caption_hashtags_only(caption: str, article_text: str, count: int) -> str:
    """Fix hashtag count without rebuilding body."""
    body = _strip_hashtag_lines(caption)
    fixed = fix_hashtag_block(body, article_text, count)
    return fixed
