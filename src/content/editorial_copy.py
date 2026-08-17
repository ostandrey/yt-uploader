"""Editorial copy for Threads (text-only) and extra Telegram formats.

Rules fallback always works. LLM is used when COPY_LLM_API_KEY is set.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.content.copy_overlap import shares_lead, split_sentences
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


_CONTRAST = re.compile(r"\b(but|still|yet|meanwhile)\b", re.I)
_HASH_OR_EMOJI = re.compile(
    r"#\w+|[\U0001F300-\U0001FAFF]|[\U0001F1E0-\U0001F1FF]|[\u2600-\u27BF]|[\uFE0F]"
)
REFLECTION_MAX = 700
REFLECTION_OVERLAP = 0.70


def _reflection_ok(text: str, banned: list[str]) -> bool:
    text = (text or "").strip()
    if not text or len(text) > REFLECTION_MAX:
        return False
    if "?" in text or _HASH_OR_EMOJI.search(text):
        return False
    if "\u2014" in text or "\u2013" in text:
        return False
    if copy_contains_banned(text):
        return False
    sentences = split_sentences(text)
    if len(sentences) < 5 or len(sentences) > 6:
        return False
    contrast_src = sentences[4] if len(sentences) >= 5 else text
    if not _CONTRAST.search(contrast_src):
        return False
    if shares_lead(text, banned, threshold=REFLECTION_OVERLAP):
        return False
    return True


def _reflection_fallback(top_entity: str, top_fact: str, secondary_entity: str, secondary_fact: str) -> str:
    top_fact = naturalize_text(top_fact).rstrip(".")
    secondary_fact = naturalize_text(secondary_fact).rstrip(".")
    top_entity = naturalize_text(top_entity)
    secondary_entity = naturalize_text(secondary_entity)
    lines = [
        f"{top_fact}.",
        f"That was the week's hard number for {top_entity}.",
        f"{secondary_fact}.",
        f"That left {secondary_entity} on the calendar, not in the outcome column.",
        "Flow moved the tape this week, but the second story was still procedural.",
    ]
    return _clean("\n".join(lines), REFLECTION_MAX)


def weekly_reflection(
    top_entity: str,
    top_fact: str,
    secondary_entity: str,
    secondary_fact: str,
    *,
    banned: Optional[list[str]] = None,
) -> str:
    """Threads editorial read. Never a recap clone. Max 700 chars."""
    banned = [item for item in (banned or []) if str(item).strip()]
    user = f"""You are the Coin Wire editorial voice for Threads. Write a 5-6 sentence weekly reflection.
Voice: dry, wire-service tone with light editorial judgment. Active voice. No em dash or en dash — use comma, period, colon, or hyphen only. Max 18 words per sentence.
Rules:
- Sentences 1-2: state the top story using ONLY this fact: "{top_entity}: {top_fact}". Do not add numbers or claims not in this fact.
- Sentences 3-4: state the secondary story using ONLY this fact: "{secondary_entity}: {secondary_fact}". Do not add numbers or claims not in this fact.
- Sentence 5: contrast what moved versus what was procedural or noise. Must contain one of: but, still, yet, meanwhile.
- Sentence 6 (optional): one forward-looking sentence about what to watch. Do not invent any date, number, or event not already known.
Forbidden phrases: "markets are watching", "traders are reacting", "this is a developing story", "bullish", "bearish", "what do you think", "crypto fam", "NFA", "DYOR".
Do not invent any number, date, or quote not present in the facts given above.
Do not ask a question. Do not use hashtags or emoji.
Output only the sentences, nothing else."""
    llm = _llm_text("Write a weekly reflection Threads post.", user, REFLECTION_MAX)
    if llm and _reflection_ok(llm, banned):
        return llm
    retry_user = (
        "Previous draft reused earlier copy. Rephrase. Keep the same facts.\n\n" + user
    )
    retry = _llm_text("Write a weekly reflection Threads post.", retry_user, REFLECTION_MAX)
    if retry and _reflection_ok(retry, banned):
        return retry
    fallback = _reflection_fallback(top_entity, top_fact, secondary_entity, secondary_fact)
    if fallback and _reflection_ok(fallback, banned):
        return fallback
    forced = (
        f"{naturalize_text(top_entity)} set the week's print.\n"
        f"The named fact stayed on the tape.\n"
        f"{naturalize_text(secondary_entity)} stayed on the calendar.\n"
        "That was process, not an outcome.\n"
        "The tape moved on flows, but policy did not."
    )
    forced = _clean(forced, REFLECTION_MAX)
    if forced and _reflection_ok(forced, banned):
        return forced
    return ""


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
