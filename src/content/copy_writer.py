"""
Optional LLM copy layer for Coin Wire social posts.

Rules-based generation is always the fallback. When COPY_LLM_API_KEY is set,
one JSON call returns Short script + IG Reel caption + carousel caption.

Threads copy is independent (news flash / editorial) — not part of this call.

Env:
  COPY_LLM_API_KEY          OpenAI or compatible API key
  COPY_LLM_MODEL            default: gpt-4o-mini
  COPY_LLM_BASE_URL         default: https://api.openai.com/v1
  COPY_LLM_ENABLED          1|0 (default 1 when key present)
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

from src.content.naturalize import naturalize_text
from src.content.short_script_generator import ShortScriptGenerator
from src.content.voice import NEWS_DESK_VOICE
from src.publishers.captions import build_caption, build_carousel_caption

log = logging.getLogger(__name__)

BANNED_PHRASES = (
    "buy now",
    "sell now",
    "100x",
    "guaranteed",
    "financial advice",
    "not financial advice",
    "pump",
    "moon",
    "delve",
    "game changer",
    "here's what you need to know",
    "in today's",
    "it's worth noting",
    "what do you think",
    "drop a comment",
)

SYSTEM_PROMPT = f"""{NEWS_DESK_VOICE}

You write English crypto news copy for YouTube Shorts and Instagram.
Output valid JSON only, matching the schema exactly."""

USER_PROMPT = """Article title: {title}
Summary: {summary}
Source: {source}
Tier: {tier}

Return JSON:
{{
  "short_title": "YouTube Short title, max 90 chars, no dash punctuation",
  "script_lines": ["3 to 5 short spoken sentences for a 18-28 sec voiceover; last line is a short CTA only", "..."],
  "ig_caption": "Instagram Reel / TikTok caption. First 125 chars are a standalone hook with an active verb and a real number if the article has one. Then 2-4 factual sentences. End with the line: Full breakdown on YouTube. Then a blank line and exactly 5 hashtags from this set only: #bitcoin #crypto #cryptonews #btc #ethereum #sec #etf #federalreserve #cryptoregulation #blockchain. Max 2200 chars. No NFA, no questions, no emoji, no em dashes.",
  "carousel_caption": "Instagram carousel caption. First 125 chars explain what the slides cover. Then 2 sentences of context. Then the line: Swipe for context. Then Source: {source}. Then exactly 4 hashtags from the same approved set. Max 2200 chars. No NFA, no questions, no em dashes."
}}"""


@dataclass
class PlatformCopy:
    short_title: str
    script: str
    ig_caption: str
    carousel_caption: str
    source: str = "rules"

    def as_content_patch(self) -> Dict[str, str]:
        return {
            "title": self.short_title,
            "script": self.script,
            "ig_caption": self.ig_caption,
            "carousel_caption": self.carousel_caption,
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
    ig = build_caption(base["title"], base.get("description", ""), max_len=2200)
    carousel = build_carousel_caption(
        base["title"],
        base.get("description", ""),
        source=source,
    )
    return PlatformCopy(
        short_title=base["title"],
        script=base["script"],
        ig_caption=ig,
        carousel_caption=carousel,
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

    script = naturalize_text("\n".join(script_lines[:5]))
    ig = _clip(str(data.get("ig_caption", "")), 2200)
    carousel = _clip(str(data.get("carousel_caption", "")), 2200)
    if len(ig) < 20:
        return None

    combined = f"{title} {script} {ig} {carousel}".lower()
    if any(bad in combined for bad in BANNED_PHRASES):
        return None

    src_words = set(re.findall(r"[a-z0-9]{4,}", article.get("title", "").lower()))
    out_words = set(re.findall(r"[a-z0-9]{4,}", combined.lower()))
    if src_words and len(src_words & out_words) < min(2, len(src_words)):
        return None

    if not carousel:
        carousel = build_carousel_caption(
            title,
            article.get("summary", ""),
            source=str(article.get("source") or ""),
        )

    return PlatformCopy(
        short_title=title,
        script=script,
        ig_caption=ig,
        carousel_caption=carousel,
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
    return _rules_copy(article, seed=seed)


def generate_content(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full Short content dict: rules metadata + platform copy (LLM or rules).
    """
    base = ShortScriptGenerator().from_article(article)
    copy = generate_platform_copy(article, seed=article.get("hash", ""))
    merged = {**base, **copy.as_content_patch()}
    return merged
