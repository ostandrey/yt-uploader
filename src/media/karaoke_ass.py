"""
Karaoke-style ASS subtitles with word highlight (\\kf) and keyword colors.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

WordEntry = Tuple[float, float, str]

WORDS_PER_LINE = 3
SENTENCE_GAP_SEC = 0.30
PLAY_RES_X = 1080
PLAY_RES_Y = 1920

# ASS colours are &HBBGGRR&
COLOR_CRYPTO = "&H00FFFF&"      # yellow — Bitcoin, Ethereum, crypto
COLOR_FED = "&H6060FF&"         # orange-red — Fed, rates
COLOR_NUMBER = "&H00FF00&"      # green — percentages, dollar amounts
COLOR_DEFAULT = "&H00FFFFFF&"   # white

CRYPTO_TERMS = {
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "altcoin", "altcoins", "blockchain", "solana", "xrp",
}
FED_TERMS = {"fed", "federal", "reserve", "rates", "rate", "hawkish", "policy"}
NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?%?$|^\d+$")


def _format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _word_color(word: str) -> str:
    clean = re.sub(r"[^\w%$-]", "", word.lower())
    if NUMBER_RE.match(clean) or "%" in word:
        return COLOR_NUMBER
    if clean in CRYPTO_TERMS or any(t in clean for t in ("bitcoin", "ethereum")):
        return COLOR_CRYPTO
    if clean in FED_TERMS:
        return COLOR_FED
    return COLOR_DEFAULT


def _display_word(word: str) -> str:
    """Mixed case — keep acronyms uppercase."""
    stripped = word.strip()
    if stripped.isupper() and len(stripped) <= 4:
        return stripped
    if stripped.lower() in ("btc", "eth", "fed"):
        return stripped.upper()
    return stripped


def _is_sentence_end(word: str) -> bool:
    return bool(re.search(r"[.!?]$", word.strip()))


def _chunk_words(
    entries: Sequence[WordEntry],
    words_per_line: int = WORDS_PER_LINE,
) -> List[List[WordEntry]]:
    """Group words for karaoke — never merge across pauses or sentence ends."""
    chunks: List[List[WordEntry]] = []
    current: List[WordEntry] = []

    for index, entry in enumerate(entries):
        current.append(entry)
        next_gap = 0.0
        if index + 1 < len(entries):
            next_gap = entries[index + 1][0] - entry[1]

        at_boundary = (
            _is_sentence_end(entry[2])
            or next_gap >= SENTENCE_GAP_SEC
            or len(current) >= words_per_line
        )
        if at_boundary:
            chunks.append(current)
            current = []

    if current:
        chunks.append(current)
    return chunks


def _build_karaoke_text(group: Sequence[WordEntry]) -> str:
    parts: List[str] = []
    for start, end, word in group:
        duration_cs = max(int((end - start) * 100), 1)
        display = _display_word(word)
        color = _word_color(word)
        parts.append(f"{{\\kf{duration_cs}\\c{color}}}{display}")
    return " ".join(parts)


def build_karaoke_ass(
    word_entries: Sequence[WordEntry],
    time_offset_sec: float = 0.0,
    words_per_line: int = WORDS_PER_LINE,
) -> str:
    if not word_entries:
        raise ValueError("No word entries for karaoke subtitles")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,96,&H00FFFFFF,&H40FFFFFF,&H00000000,&HE0000000,-1,0,0,0,100,100,0,0,1,10,6,2,50,50,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: List[str] = []
    for group in _chunk_words(word_entries, words_per_line):
        start = group[0][0] + time_offset_sec
        end = group[-1][1] + time_offset_sec
        text = _build_karaoke_text(group)
        events.append(
            f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},"
            f"Default,,0,0,0,,{{\\fad(80,80)\\bord10\\shad6\\blur0}}{text}"
        )

    return header + "\n".join(events) + "\n"
