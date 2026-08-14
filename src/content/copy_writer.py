"""
Optional LLM copy layer for Coin Wire social posts.

Rules-based generation is always the fallback. When COPY_LLM_API_KEY is set,
one JSON call returns Short script + IG Reel caption + carousel caption.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from src.content.copy_polish import (
    llm_copy_passes_qa,
    polish_carousel_caption,
    polish_ig_caption,
    polish_script_lines,
)
from src.content.naturalize import naturalize_text
from src.content.short_script_generator import ShortScriptGenerator
from src.content.voice import NEWS_DESK_VOICE, SHORT_SCRIPT_CTA
from src.publishers.captions import build_caption, build_carousel_caption, build_tiktok_caption

log = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""{NEWS_DESK_VOICE}

You write English crypto news copy for YouTube Shorts and Instagram.
Output valid JSON only, matching the schema exactly."""

USER_PROMPT = """Article title: {title}
Summary: {summary}
Source: {source}
Tier: {tier}

Return JSON:
{{
  "short_title": "YouTube title, max 90 chars. Start with number or name when possible.",
  "script_lines": [
    "Line 1: number or name + what happened (max 18 words).",
    "Line 2-4: one fact each, max 18 words per line.",
    "Final line exactly: {cta}"
  ],
  "ig_caption": "IG Reel caption only, not TikTok. First 125 chars: hook with number or name. Then 2-4 fact sentences, one per line. Then blank line, then exactly: Full breakdown on YouTube. Then blank line, then exactly 5 hashtags. Pick 4 from #bitcoin #crypto #cryptonews #btc #ethereum #sec #etf #federalreserve #cryptoregulation #blockchain plus 1 topic tag (#ripple #solana #binance #coinbase) only if the article is clearly about that ticker. Count hashtags before output. Max 2200 chars.",
  "carousel_caption": "Carousel caption. Line 1: what the slides cover without spoiling. Optional line 2: one intriguing fact. Then: Swipe for context. Then: Source: {source}. Then exactly 4 hashtags from the approved set. Max 2200 chars."
}}"""


@dataclass
class PlatformCopy:
    short_title: str
    script: str
    ig_caption: str
    carousel_caption: str
    tiktok_caption: str = ""
    source: str = "rules"

    def as_content_patch(self) -> Dict[str, str]:
        tiktok = self.tiktok_caption or build_tiktok_caption(
            self.ig_caption, title=self.short_title, article_text=self.ig_caption
        )
        return {
            "title": self.short_title,
            "script": self.script,
            "ig_caption": self.ig_caption,
            "carousel_caption": self.carousel_caption,
            "tiktok_caption": tiktok,
            "threads_text": "",
            "threads_question": "",
            "copy_source": self.source,
        }


def llm_configured() -> bool:
    load_dotenv()
    if os.getenv("COPY_LLM_ENABLED", "").strip().lower() in ("0", "false", "off", "no"):
        return False
    key = os.getenv("COPY_LLM_API_KEY", "").strip()
    return bool(key)


def chat_json(system: str, user: str, *, timeout: int = 45) -> Optional[dict]:
    """One OpenAI-compatible JSON chat completion. None on any failure."""
    load_dotenv()
    api_key = os.getenv("COPY_LLM_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.getenv("COPY_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    base_url = os.getenv("COPY_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.35,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
        if isinstance(data, dict):
            log.info("LLM copy ok model=%s", model)
            return data
        return None
    except Exception as exc:
        log.warning("LLM JSON call failed (model=%s): %s", model, exc)
        return None


def _rules_copy(article: Dict[str, Any], *, seed: str = "") -> PlatformCopy:
    base = ShortScriptGenerator().from_article(article)
    source = str(article.get("source") or "")
    article_blob = f"{base['title']} {base.get('description', '')}"
    ig = build_caption(base["title"], base.get("description", ""), max_len=2200)
    carousel = build_carousel_caption(
        base["title"],
        base.get("description", ""),
        source=source,
    )
    tiktok = build_tiktok_caption(
        ig, title=base["title"], article_text=article_blob
    )
    return PlatformCopy(
        short_title=base["title"],
        script=base["script"],
        ig_caption=ig,
        carousel_caption=carousel,
        tiktok_caption=tiktok,
        source="rules",
    )


def _clip(text: str, max_len: int) -> str:
    text = naturalize_text(text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:- ") + "..."


def _validate_llm_payload(data: dict, article: Dict[str, Any]) -> Optional[PlatformCopy]:
    title = _clip(str(data.get("short_title", "")), 90)
    lines = data.get("script_lines") or []
    if not isinstance(lines, list):
        return None
    script_lines = [_clip(str(line), 160) for line in lines if str(line).strip()]
    script_lines = [line for line in script_lines if line]
    if len(title) < 12 or len(script_lines) < 3:
        return None

    article_blob = f"{article.get('title', '')} {article.get('summary', '')}"
    source = str(article.get("source") or "news")

    script = polish_script_lines(script_lines)
    ig = polish_ig_caption(_clip(str(data.get("ig_caption", "")), 2200), article_blob)
    carousel = polish_carousel_caption(
        _clip(str(data.get("carousel_caption", "")), 2200),
        article_blob,
        source=source,
    )
    if len(ig) < 20:
        return None

    combined = f"{title} {script} {ig} {carousel}"
    if not llm_copy_passes_qa(combined):
        return None

    src_words = set(re.findall(r"[a-z0-9]{4,}", article.get("title", "").lower()))
    out_words = set(re.findall(r"[a-z0-9]{4,}", combined.lower()))
    if src_words and len(src_words & out_words) < min(2, len(src_words)):
        return None

    return PlatformCopy(
        short_title=title,
        script=script,
        ig_caption=ig,
        carousel_caption=carousel,
        tiktok_caption=build_tiktok_caption(ig, title=title, article_text=article_blob),
        source="llm",
    )


def _call_llm(article: Dict[str, Any]) -> Optional[PlatformCopy]:
    if not llm_configured():
        return None
    tier = str(article.get("tier", "standard"))
    user_msg = USER_PROMPT.format(
        title=naturalize_text(article.get("title", "")),
        summary=naturalize_text(article.get("summary", ""))[:800],
        source=article.get("source", "news"),
        tier=tier,
        cta=SHORT_SCRIPT_CTA,
    )
    data = chat_json(SYSTEM_PROMPT, user_msg)
    if not data:
        return None
    return _validate_llm_payload(data, article)


def generate_platform_copy(
    article: Dict[str, Any],
    *,
    seed: str = "",
) -> PlatformCopy:
    """Rules fallback; optional LLM rewrite when configured."""
    if llm_configured():
        llm_copy = _call_llm(article)
        if llm_copy:
            return llm_copy
        fallback = _rules_copy(article, seed=seed)
        fallback.source = "rules_fallback"
        return fallback
    return _rules_copy(article, seed=seed)


def generate_content(article: Dict[str, Any]) -> Dict[str, Any]:
    """Full Short content dict: rules metadata + platform copy (LLM or rules)."""
    base = ShortScriptGenerator().from_article(article)
    copy = generate_platform_copy(article, seed=article.get("hash", ""))
    merged = {**base, **copy.as_content_patch()}
    return merged
