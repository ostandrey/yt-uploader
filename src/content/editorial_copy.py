"""Editorial copy for Threads (text-only) and extra Telegram formats.

Rules fallback always works. LLM is used when COPY_LLM_API_KEY is set.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.content.copy_overlap import shares_lead
from src.content.copy_writer import chat_json, llm_configured
from src.content.naturalize import naturalize_text
from src.content.voice import NEWS_DESK_VOICE

from src.content.voice import NEWS_DESK_VOICE, copy_contains_banned


def _clip(text: str, max_len: int) -> str:
    text = naturalize_text((text or "").strip())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:- ") + "..."


def _clean(text: str, max_len: int) -> str:
    text = _clip(text, max_len)
    if copy_contains_banned(text):
        return ""
    return text


def _first_sentence(text: str) -> str:
    text = naturalize_text(text or "")
    part = text.split(".")[0].strip()
    if part and not part.endswith("."):
        part += "."
    return part


def _llm_text(task: str, user: str, max_len: int) -> str:
    if not llm_configured():
        return ""
    system = f"{NEWS_DESK_VOICE}\n\n{task}\nReturn JSON {{\"text\": \"...\"}}."
    data = chat_json(system, user)
    if not data:
        return ""
    raw = str(data.get("text") or data.get("post") or "").strip()
    return _clean(raw, max_len)


def news_flash(article: dict[str, Any]) -> str:
    title = naturalize_text(article.get("title") or "")
    summary = _first_sentence(article.get("summary") or "")
    user = f"""Rules:
- Max 500 characters.
- First sentence: the single most important fact. Include a number or name if available.
- Second sentence: one line of context.
- No CTA to YouTube. No engagement questions. No disclaimer.
- No hashtags unless regulatory (then one only from #bitcoin #sec #crypto).
- No em dashes.

Article title: {title}
Article summary: {article.get("summary") or ""}
Tier: {article.get("tier") or "strong"}"""
    llm = _llm_text("Write a standalone Threads news flash. Not linked to a video.", user, 500)
    if llm:
        return llm
    if summary and summary.lower() not in title.lower():
        return _clip(f"{title}\n\n{summary}", 500)
    return _clip(title, 500)


def opinion_hook(article: dict[str, Any]) -> str:
    title = naturalize_text(article.get("title") or "")
    user = f"""Rules:
- Max 240 characters.
- One bold declarative statement. Not a question. Not a fact dump.
- Based strictly on today's article. No invented claims.
- Slightly contrarian or non-obvious. Not clickbait.
- No hashtags. No emoji. No NFA. No "I think". Present tense.
- No em dashes.

Article title: {title}
Article summary: {article.get("summary") or ""}"""
    llm = _llm_text("Write a Threads opinion hook.", user, 240)
    if llm:
        return llm
    return _clip(f"{title.rstrip('.')} is the part of this week that actually matters.", 240)


def _poll_shaped(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 3:
        return True
    blob = "\n".join(lines)
    return bool(re.search(r"(?im)^\s*(?:[ab]|1|2)[).:\-]\s+\S", blob))


def _weak_question(text: str) -> bool:
    if _poll_shaped(text):
        return True
    lower = text.lower()
    if re.search(r"what happens (next|after)|what actually moves next|who actually captures the next", lower):
        return True
    if not re.search(r"\b(which|who is|who are|versus|\bvs\.?\b|actually)\b", lower):
        return True
    return False


def _question_fallback(title: str, summary: str) -> str:
    blob = f"{title} {summary}"
    money = re.search(r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:billion|million|[BMKTbmkt])?", blob, re.I)
    agency = re.search(
        r"\b(CFTC|SEC|Fed|FOMC|BlackRock|Fidelity|Coinbase|Binance)\b", blob
    )
    entity = agency.group(0) if agency else (title.split()[0] if title else "This")
    if agency and re.search(r"agenda|meeting|committee|AI|artificial", blob, re.I):
        return _clip(
            f"If {entity} is grouping crypto with AI and prediction markets on one agenda, "
            "which one actually drives the session?",
            180,
        )
    if money:
        return _clip(
            f"If {entity} just printed {money.group(0).strip()}, who is actually absorbing the other side?",
            180,
        )
    return _clip(
        f"If {entity} is the name on this tape, who is actually on the other side versus the headline?",
        180,
    )


def question_post(article: dict[str, Any]) -> str:
    title = naturalize_text(article.get("title") or "")
    summary = naturalize_text(article.get("summary") or "")
    user = f"""You write one Threads post: a single market question. Threads has no poll.

Format: one question. Optional second sentence of context. No option lines.

Rules:
- Max 180 characters. Must name a specific entity or number from the article.
- Comparative or causal frame only: "which ... actually ...", "who is ... versus ...", "who is actually absorbing".
- Forbidden: "what happens next", "what happens after", "who actually captures the next move", yes/no, A/B lines, "Does this change the setup?", "What do you think?", "Bullish or bearish?".
- No hashtags, emoji, preamble, em dashes, "I think".

Good:
If the CFTC is grouping crypto with AI and prediction markets on one agenda, which one actually drives the Aug. 20 discussion?
If Fidelity keeps 85% of ETH staking rewards, who is the ETF actually for?

Bad:
After BlackRock Bitcoin ETF inflows hit $4.6B, what happens next?

Article title: {title}
Article summary: {summary}"""
    llm = _llm_text("Write a Threads question with a which/who-actually frame. No poll options.", user, 180)
    if llm and "?" in llm and "change the setup" not in llm.lower() and not _weak_question(llm):
        return llm
    return _question_fallback(title, summary)


def weekly_recap(events_list: str) -> str:
    user = f"""Rules:
- Max 500 characters.
- Header line exactly: This week in crypto:
- Then 4-5 bullet lines starting with "- " (hyphen + space). One fact per line.
- Final line: Watch next week: + one sentence about what to monitor.
- No hashtags. No emoji. No opinions or predictions. No em dashes.
- Use ONLY the events listed. Do not invent extra events.

Weekly events list:
{events_list}"""
    llm = _llm_text("Write a weekly recap Threads post.", user, 500)
    if llm:
        return llm
    bullets = [line.strip() for line in (events_list or "").splitlines() if line.strip()]
    if not bullets:
        return ""
    normalized = []
    for line in bullets[:5]:
        item = line.lstrip("-–— ").strip()
        normalized.append(f"- {item}" if item else line)
    body = "This week in crypto:\n" + "\n".join(normalized)
    return _clip(body, 500)


def telegram_context(article: dict[str, Any]) -> str:
    title = naturalize_text(article.get("title") or "")
    summary = naturalize_text(article.get("summary") or "")
    lead = _first_sentence(summary)
    user = f"""Rules:
- Max 600 characters.
- Header: Context:
- 4-6 sentences only.
- Structure: background that is NOT in the breaking post (1-2) then what led here (1-2) then what to watch next (1-2).
- Do NOT repeat the article title.
- Do NOT reuse the lead sentence of the summary. Paraphrase. The operator already posted the breaking item.
- No price predictions. No bullish/bearish. Facts and process only.
- No hashtags. English. No em dashes.

Breaking article title: {title}
Lead sentence (do not repeat): {lead}
Article summary: {summary}"""
    llm = _llm_text("Write a Telegram context post that follows a breaking news item.", user, 600)
    if llm and not shares_lead(llm, [title, lead]):
        return llm
    return _clip(
        "Context:\n\nThis is a follow-on to the breaking item, not a restatement of the headline. "
        "The next official print or filing is the document that matters. "
        "Treat today's alert as a calendar marker until that docket is public.",
        600,
    )


def telegram_poll(article: dict[str, Any]) -> Optional[dict[str, Any]]:
    title = naturalize_text(article.get("title") or "")
    system = (
        f"{NEWS_DESK_VOICE}\n\nGenerate a Telegram poll. "
        'Return JSON {"question": "...", "options": ["A", "B", "C"]}.'
    )
    user = f"""Rules:
- Question: max 100 characters. Neutral, factual framing.
- Exactly 3 answer options. Each max 40 characters.
- Options must be mutually exclusive.
- No "Other" or "I don't know".
- No price predictions as options. No em dashes.

Article title: {title}
Article summary: {article.get("summary") or ""}"""
    if llm_configured():
        data = chat_json(system, user)
        if data:
            question = _clean(str(data.get("question") or ""), 100)
            options = data.get("options") or []
            if question and isinstance(options, list):
                cleaned = [_clip(str(opt), 40) for opt in options if str(opt).strip()]
                if len(cleaned) >= 3:
                    return {"question": question, "options": cleaned[:3]}
    return {
        "question": _clip(f"What happens next after: {title}", 100),
        "options": ["Settles in days", "Stays in the tape this month", "Gets overwritten fast"],
    }


def telegram_weekly_digest(events_list: str, upcoming_list: str = "") -> str:
    user = f"""Rules:
- Header line: Week in review
- 5 numbered items. Each: entity name + one sentence of fact.
- If upcoming events are provided, add "This week watch:" with 2-3 bullets using "- ".
- If upcoming is empty, omit that section. Do not invent dates.
- Max 900 characters. No opinions, no predictions, no price targets. English. No em dashes.

Events this week:
{events_list}

Upcoming events:
{upcoming_list or "(none)"}"""
    llm = _llm_text("Write a weekly digest post for a Telegram channel.", user, 900)
    if llm:
        return llm
    bullets = [line.strip("—–- ").strip() for line in (events_list or "").splitlines() if line.strip()]
    if not bullets:
        return ""
    lines = ["Week in review", ""]
    for index, item in enumerate(bullets[:5], start=1):
        lines.append(f"{index}. {item}")
    if upcoming_list.strip() and "none" not in upcoming_list.lower():
        lines.append("")
        lines.append("This week watch:")
        for line in upcoming_list.splitlines():
            if line.strip():
                lines.append(f"- {line.strip()}")
    return _clip("\n".join(lines), 900)
