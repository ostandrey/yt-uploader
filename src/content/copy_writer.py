"""
Optional LLM copy layer for Coin Wire social posts.

Rules-based generation is always the fallback. When COPY_LLM_API_KEY is set,
one cheap JSON call rewrites Short script + Threads + Instagram caption.

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
from src.publishers.captions import (
    build_caption,
    build_threads_text,
    pick_engagement_question,
    should_add_engagement_question,
)

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
)

SYSTEM_PROMPT = """You write English crypto news copy for Coin Wire (Telegram, YouTube Shorts, Threads, Instagram).

Rules:
- Use ONLY facts from the provided article. Do not invent numbers, quotes, or events.
- Tone: clear, professional, newsroom. No hype, no shilling.
- Never use em dashes. Use commas, periods, or hyphens instead.
- No "buy now", "100x", or investment advice.
- Output valid JSON only, matching the schema exactly."""


USER_PROMPT = """Article title: {title}
Summary: {summary}
Source: {source}
Tier: {tier}

Return JSON:
{{
  "short_title": "YouTube Short title, max 90 chars",
  "script_lines": ["5 to 7 short spoken sentences for a 25-35 sec voiceover", "..."],
  "threads_text": "Threads post, max 420 chars, headline + 1-2 factual lines",
  "threads_question": "optional engagement question or empty string",
  "ig_caption": "Instagram caption, max 500 chars, factual + 3-5 hashtags at end"
}}"""


@dataclass
class PlatformCopy:
    short_title: str
    script: str
    threads_text: str
    threads_question: str
    ig_caption: str
    source: str = "rules"

    def as_content_patch(self) -> Dict[str, str]:
        return {
            "title": self.short_title,
            "script": self.script,
            "threads_text": self.threads_text,
            "threads_question": self.threads_question,
            "ig_caption": self.ig_caption,
            "copy_source": self.source,
        }


def llm_configured() -> bool:
    load_dotenv()
    if os.getenv("COPY_LLM_ENABLED", "").strip().lower() in ("0", "false", "off", "no"):
        return False
    key = os.getenv("COPY_LLM_API_KEY", "").strip()
    return bool(key)


def _rules_copy(article: Dict[str, Any], *, seed: str = "") -> PlatformCopy:
    base = ShortScriptGenerator().from_article(article)
    seed = seed or article.get("hash") or base["title"]
    question = ""
    if should_add_engagement_question(seed, 0.35):
        question = pick_engagement_question(seed)
    threads = build_threads_text(
        base["title"],
        base.get("description", ""),
        engagement_question=question,
    )
    ig = build_caption(base["title"], base.get("description", ""), max_len=500)
    return PlatformCopy(
        short_title=base["title"],
        script=base["script"],
        threads_text=threads,
        threads_question=question,
        ig_caption=ig,
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
    if len(title) < 12 or len(script_lines) < 4:
        return None

    script = naturalize_text("\n".join(script_lines[:7]))
    threads = _clip(str(data.get("threads_text", "")), 420)
    question = _clip(str(data.get("threads_question", "") or ""), 120)
    ig = _clip(str(data.get("ig_caption", "")), 500)

    combined = f"{title} {script} {threads} {ig} {question}".lower()
    if any(bad in combined for bad in BANNED_PHRASES):
        return None

    # Require some overlap with source headline words (anti-hallucination guard)
    src_words = set(re.findall(r"[a-z0-9]{4,}", article.get("title", "").lower()))
    out_words = set(re.findall(r"[a-z0-9]{4,}", combined.lower()))
    if src_words and len(src_words & out_words) < min(2, len(src_words)):
        return None

    if question and question not in threads:
        threads = _clip(f"{threads}\n\n{question}", 420)

    return PlatformCopy(
        short_title=title,
        script=script,
        threads_text=threads,
        threads_question=question,
        ig_caption=ig,
        source="llm",
    )


def _call_llm(article: Dict[str, Any]) -> Optional[PlatformCopy]:
    load_dotenv()
    api_key = os.getenv("COPY_LLM_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("COPY_LLM_MODEL", "gpt-4o-mini").strip()
    base_url = os.getenv("COPY_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    tier = str(article.get("tier", "standard"))

    user_msg = USER_PROMPT.format(
        title=naturalize_text(article.get("title", "")),
        summary=naturalize_text(article.get("summary", ""))[:800],
        source=article.get("source", "news"),
        tier=tier,
    )

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
        return _validate_llm_payload(data, article)
    except Exception as exc:
        log.warning("LLM copy generation failed, using rules: %s", exc)
        return None


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
