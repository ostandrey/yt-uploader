"""
Turn a crypto news article into a Coin Wire Short script + metadata.
Rule-based (no LLM) so the daily pipeline runs without extra API keys.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.content.naturalize import naturalize_text

WORD_NUMBERS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 15: "fifteen", 20: "twenty",
}

ASSET_ALIASES = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "crypto": "crypto", "cryptocurrency": "crypto",
}

DIRECTION_WORDS = {
    "drop": "dropped", "drops": "dropped", "dropped": "dropped", "fall": "fell",
    "falls": "fell", "fell": "fell", "decline": "declined", "declined": "declined",
    "slide": "slid", "slid": "slid", "sink": "sank", "sank": "sank",
    "rise": "rose", "rises": "rose", "rose": "rose", "rally": "rallied",
    "rallied": "rallied", "gain": "gained", "gained": "gained", "surge": "surged",
    "surged": "surged", "jump": "jumped", "jumped": "jumped",
}


def _pct_to_words(value: float) -> str:
    whole = int(round(value))
    if whole in WORD_NUMBERS:
        return WORD_NUMBERS[whole]
    return str(whole)


def _extract_asset_moves(text: str) -> List[Tuple[str, float, str]]:
    """Return [(asset, percent, direction)] from article text."""
    lower = text.lower()
    moves: List[Tuple[str, float, str]] = []

    patterns = [
        r"(bitcoin|btc|ethereum|eth)\s+(?:\w+\s+){0,6}?"
        r"(drop(?:ped|s)?|fall(?:s|en)?|fell|declin(?:e|ed|es)|"
        r"rise(?:s|n)?|rose|rall(?:y|ied|ies)|gain(?:ed|s)?|surge(?:d|s)?|jump(?:ed|s)?)"
        r"\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)",
        r"(bitcoin|btc|ethereum|eth)\s+(?:is\s+)?(?:down|up)\s+(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s+(?:drop|fall|decline|rise|rally|gain|surge)\s+in\s+"
        r"(bitcoin|btc|ethereum|eth)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, lower):
            groups = match.groups()
            if len(groups) == 3:
                asset_raw, direction_raw, pct_raw = groups
            else:
                pct_raw, asset_raw = groups
                direction_raw = "drop" if "drop" in match.group(0) or "fall" in match.group(0) else "rise"

            asset = ASSET_ALIASES.get(asset_raw, asset_raw)
            pct = float(pct_raw)
            direction = "down" if any(
                w in direction_raw for w in ("drop", "fall", "declin", "sink", "down")
            ) else "up"
            moves.append((asset, pct, direction))

    generic_pct = re.search(
        r"(bitcoin|btc|ethereum|eth|crypto).{0,60}?(\d+(?:\.\d+)?)\s*%",
        lower,
    )
    if not moves and generic_pct:
        asset = ASSET_ALIASES.get(generic_pct.group(1), generic_pct.group(1))
        moves.append((asset, float(generic_pct.group(2)), "down"))

    seen: set[str] = set()
    unique: List[Tuple[str, float, str]] = []
    for asset, pct, direction in moves:
        key = f"{asset}:{pct}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((asset, pct, direction))
    return unique[:2]


def _topic_context(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(k in text for k in ("fed", "federal reserve", "interest rate", "powell")):
        return "Federal Reserve policy"
    if any(k in text for k in ("sec", "regulation", "regulatory", "lawsuit")):
        return "regulatory headlines"
    if any(k in text for k in ("etf", "approval", "blackrock")):
        return "ETF flows"
    if any(k in text for k in ("defi", "protocol", "hack", "exploit")):
        return "DeFi developments"
    if any(k in text for k in ("ethereum", "eth")):
        return "Ethereum ecosystem news"
    return "breaking crypto market news"


def _short_title(article_title: str, moves: List[Tuple[str, float, str]]) -> str:
    if moves:
        asset, pct, direction = moves[0]
        label = "Bitcoin" if asset == "bitcoin" else asset.capitalize()
        arrow = "Drops" if direction == "down" else "Rises"
        headline = f"{label} {arrow} {int(round(pct))}%"
        remainder = article_title.split("-")[0].strip()
        if len(remainder) > 20 and len(headline) < 60:
            short_remainder = remainder[:40].strip()
            return f"{headline} - {short_remainder}"[:100]
        return headline[:100]

    title = article_title.strip()
    if len(title) <= 90:
        return title
    for splitter in (" as ", " - ", ", "):
        if splitter in title:
            return title.split(splitter, 1)[0].strip()[:100]
    return _truncate_at_words(title, 87, end="")


def _move_sentence(asset: str, pct: float, direction: str) -> str:
    pct_words = _pct_to_words(pct)
    verb = "dropped" if direction == "down" else "rose"
    if asset == "bitcoin":
        return f"Bitcoin {verb} {pct_words} percent on the latest headline."
    if asset == "ethereum":
        return f"Ethereum {verb} about {pct_words} percent, tracking the broader move."
    return f"Crypto markets moved about {pct_words} percent on the news."


GENERIC_TITLE_PATTERNS = [
    "what happened in crypto",
    "today in crypto",
    "crypto today",
    "top stories",
    "week in review",
    "daily roundup",
    "news roundup",
    "here's what",
    "here is what",
]


def _is_generic_roundup(title: str) -> bool:
    lower = title.lower()
    return any(pattern in lower for pattern in GENERIC_TITLE_PATTERNS)


def _truncate_at_words(text: str, max_len: int, end: str = ".") -> str:
    """Cut text at a word boundary — never mid-word."""
    text = text.strip().rstrip(".")
    if len(text) <= max_len:
        return text + end

    cut = text[:max_len]
    last_space = cut.rfind(" ")
    if last_space > 20:
        cut = cut[:last_space]
    return cut.rstrip(".,;:-") + end


def _money_to_words(text: str) -> Optional[str]:
    match = re.search(
        r"\$\s*([\d,.]+)\s*(million|billion|thousand)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    raw = match.group(1).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None

    unit = (match.group(2) or "").lower()
    whole = int(round(value))

    if unit == "billion":
        return f"{_pct_to_words(whole)} billion dollars"
    if unit == "million":
        if whole in WORD_NUMBERS:
            return f"{WORD_NUMBERS[whole]} million dollars"
        return f"{whole} million dollars"
    if unit == "thousand":
        return f"{whole} thousand dollars"
    return f"{whole} dollars"


def _spoken_hook(title: str, summary: str, context: str) -> str:
    """Rewrite headline into a short, natural voiceover line."""
    combined = f"{title} {summary}"
    lower = combined.lower()

    money = _money_to_words(combined)

    if "etf" in lower:
        if "outflow" in lower and ("snap" in lower or "streak" in lower or "end" in lower):
            if money:
                return (
                    f"Spot Bitcoin ETFs snapped a five-day outflow streak, "
                    f"pulling in {money} on Friday."
                )
            return "Spot Bitcoin ETFs snapped a five-day outflow streak with fresh inflows Friday."
        if "inflow" in lower and money:
            return f"Spot Bitcoin ETFs pulled in {money} on the latest session."
        if "outflow" in lower and money:
            return f"Spot Bitcoin ETFs saw {money} in outflows on the latest session."
        return "Spot Bitcoin ETF flows are shifting again on the latest session."

    if "fed" in lower or "interest rate" in lower or "federal reserve" in lower:
        return "Federal Reserve policy is moving crypto prices again."

    if "sec" in lower or "regulat" in lower:
        return "A new regulatory headline is hitting crypto markets."

    if "bitcoin" in lower and money:
        return f"Bitcoin is in focus after a move tied to {money}."

    if "ethereum" in lower or " ether " in lower:
        return "Ethereum is leading the next crypto market move."

    if "bitcoin" in lower:
        return "Bitcoin is driving today's crypto headline."

    # Fall back to the first clean clause of the title, never mid-word.
    clause = title.strip().rstrip(".")
    for splitter in (" as ", " - ", ", "):
        if splitter in clause:
            clause = clause.split(splitter, 1)[0].strip()
            break
    return _truncate_at_words(clause, 72)


def _spoken_context_line(summary: str) -> str:
    if not summary:
        return "Markets are reacting to the latest headline."

    line = summary.strip()
    line = re.sub(
        r"\$\s*[\d,.]+\s*(million|billion|thousand)?",
        lambda m: _money_to_words(m.group(0)) or "",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(r"\s+", " ", line).strip(" ,;")

    if len(line) > 100:
        line = _truncate_at_words(line, 100, end=".")
    elif not line.endswith("."):
        line += "."
    return line


def _wall_street_detail(title: str, summary: str) -> Optional[str]:
    lower = f"{title} {summary}".lower()
    if "wall street" not in lower:
        return None
    if "ethereum" in lower or " ether " in lower:
        return (
            "Wall Street firms are moving past crypto pilots "
            "into deeper Ethereum exposure."
        )
    return "Wall Street is stepping deeper into digital asset markets."


def _topic_detail(title: str, summary: str, context: str) -> Optional[str]:
    lower = f"{title} {summary}".lower()
    if "blackrock" in lower or "fidelity" in lower:
        return "Major fund managers including BlackRock and Fidelity are driving the flow."
    if "institution" in lower or "bank" in lower:
        return "Institutional players are behind this move, not just retail traders."
    if context == "regulatory headlines":
        return "Regulation headlines can move prices faster than fundamentals."
    if context == "Federal Reserve policy":
        return "Rate expectations still dominate risk assets including crypto."
    return None


def _market_impact(context: str) -> str:
    impacts = {
        "ETF flows": (
            "Institutional ETF flows often set the tone for Bitcoin's next move."
        ),
        "Ethereum ecosystem news": (
            "When institutions lean into Ethereum, altcoins often follow the trend."
        ),
        "Federal Reserve policy": (
            "Crypto stays highly sensitive to every Fed policy signal."
        ),
        "regulatory headlines": (
            "Traders are pricing in regulatory risk across major exchanges."
        ),
        "DeFi developments": (
            "DeFi headlines can spill over into broader crypto sentiment quickly."
        ),
    }
    return impacts.get(
        context,
        "This headline could shift short-term momentum across crypto markets.",
    )


def _summary_sentences(summary: str, max_count: int = 2) -> List[str]:
    if not summary:
        return []

    text = summary.strip()
    text = re.sub(
        r"\$\s*[\d,.]+\s*(million|billion|thousand)?",
        lambda m: _money_to_words(m.group(0)) or "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip()

    parts = re.split(r"(?<=[.!?])\s+", text)
    results: List[str] = []
    for part in parts:
        part = part.strip(" ,;")
        if len(part) < 25:
            continue
        if len(part) > 115:
            part = _truncate_at_words(part, 115, end=".")
        elif not part.endswith("."):
            part += "."
        results.append(part)
        if len(results) >= max_count:
            break

    if not results and text:
        line = _truncate_at_words(text, 115, end=".")
        results.append(line)
    return results


class ShortScriptGenerator:
    def from_article(self, article: Dict) -> Dict:
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        link = article.get("link", "").strip()
        source = article.get("source", "news").replace("_", " ").title()

        combined = f"{title}. {summary}"
        moves = _extract_asset_moves(combined)
        context = _topic_context(title, summary)

        sentences: List[str] = []

        # 1. Hook — главный факт
        if moves:
            sentences.append(_move_sentence(*moves[0]))
            if len(moves) > 1:
                sentences.append(_move_sentence(*moves[1]))
        else:
            sentences.append(_spoken_hook(title, summary, context))

        # 2. Деталь из заголовка / темы
        extra = _wall_street_detail(title, summary) or _topic_detail(title, summary, context)
        if extra:
            sentences.append(extra)

        # 3. Почему это важно рынку
        if "etf" in combined.lower():
            if "ether" in combined.lower() or "ethereum" in combined.lower():
                sentences.append("Ethereum funds are seeing mixed flows alongside Bitcoin.")
            else:
                sentences.append("ETF flows remain the main driver for Bitcoin price action.")
        elif "fed" in combined.lower() or "rate" in combined.lower():
            sentences.append("Markets are watching Federal Reserve policy for the next cue.")
        elif "sec" in combined.lower() or "regulat" in combined.lower():
            sentences.append("Regulators remain in focus as crypto prices react quickly.")
        else:
            sentences.append(f"Traders are reacting to {context.lower()}.")

        # 4–5. Факты из summary статьи (пересказ, не копипаст заголовка)
        for fact in _summary_sentences(summary, max_count=2):
            if fact not in sentences:
                sentences.append(fact)

        # 6. Рыночный вывод — добиваем до ~25–35 сек
        if len(sentences) < 5:
            sentences.append(_market_impact(context))

        # 7. CTA
        sentences.append("Get the next shift. Follow Coin Wire for daily market moves.")

        script = "\n".join(sentences[:7])
        short_title = _short_title(title, moves)

        keywords = self._keywords(combined, moves)
        description = self._description(short_title, summary, link, source)

        return {
            "title": naturalize_text(short_title),
            "script": naturalize_text(script),
            "keywords": keywords,
            "description": naturalize_text(description),
            "source_article": naturalize_text(title),
            "source_link": link,
        }

    def _keywords(self, text: str, moves: List[Tuple[str, float, str]]) -> List[str]:
        keywords = ["bitcoin", "cryptocurrency", "stock market"]
        lower = text.lower()
        if any(a == "ethereum" for a, _, _ in moves) or "ethereum" in lower:
            keywords.append("ethereum")
        if any(k in lower for k in ("fed", "federal reserve", "interest rate")):
            keywords.extend(["federal reserve", "interest rates"])
        if "sec" in lower:
            keywords.append("sec regulation")
        return keywords[:6]

    def _description(
        self, title: str, summary: str, link: str, source: str
    ) -> str:
        body = summary[:300] if summary else title
        lines = [
            body,
            "",
            f"Source: {source}",
            f"Read more: {link}" if link else "",
            "",
            "Follow @coinwirenews for daily crypto market moves.",
            "",
            "#bitcoin #ethereum #cryptonews #crypto #shorts #coinwire",
        ]
        return "\n".join(line for line in lines if line)
