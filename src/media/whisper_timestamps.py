"""
Refine word-level timestamps using faster-whisper on generated voiceover.
Falls back gracefully if the package or model is unavailable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

WordEntry = Tuple[float, float, str]

WORD_ALIASES = {
    "percent": "%",
    "four": "4",
    "three": "3",
    "two": "2",
    "one": "1",
    "five": "5",
}


def _normalize_token(token: str) -> str:
    clean = re.sub(r"[^\w%$]", "", token.lower())
    return WORD_ALIASES.get(clean, clean)


def _tokens_match(script_token: str, whisper_token: str) -> bool:
    a = _normalize_token(script_token)
    b = _normalize_token(whisper_token)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    return False


def _align_script_to_whisper(
    script_words: List[str],
    whisper_words: List[Tuple[float, float, str]],
) -> List[WordEntry]:
    """Greedy alignment: map each script word to the best whisper timestamp."""
    if not whisper_words:
        return []

    aligned: List[WordEntry] = []
    whisper_index = 0

    for script_word in script_words:
        matched_index: Optional[int] = None
        search_limit = min(whisper_index + 6, len(whisper_words))

        for candidate in range(whisper_index, search_limit):
            if _tokens_match(script_word, whisper_words[candidate][2]):
                matched_index = candidate
                break

        if matched_index is not None:
            start, end, _ = whisper_words[matched_index]
            if aligned:
                prev_end = aligned[-1][1]
                start = max(start, prev_end)
            if end <= start:
                end = start + 0.12
            aligned.append((start, end, script_word))
            whisper_index = matched_index + 1
            continue

        if aligned:
            prev_end = aligned[-1][1]
            start = prev_end
            end = start + 0.18
        elif whisper_index < len(whisper_words):
            start = whisper_words[whisper_index][0]
            end = start + 0.18
            whisper_index += 1
        else:
            start = aligned[-1][1] if aligned else 0.0
            end = start + 0.18

        aligned.append((start, end, script_word))

    return _smooth_word_gaps(aligned)


def _smooth_word_gaps(entries: List[WordEntry], pause_threshold: float = 0.30) -> List[WordEntry]:
    """Remove overlaps; preserve natural pauses between sentences."""
    if not entries:
        return entries

    smoothed: List[WordEntry] = []
    for index, (start, end, word) in enumerate(entries):
        if smoothed:
            prev_end = smoothed[-1][1]
            gap = start - prev_end
            if gap < 0:
                start = prev_end
            elif gap >= pause_threshold:
                # Keep the pause — don't stretch words across sentence breaks
                pass
        min_dur = 0.08
        max_dur = 0.55
        duration = max(end - start, min_dur)
        duration = min(duration, max_dur)
        end = start + duration
        smoothed.append((start, end, word))

    return smoothed


def refine_word_timestamps(
    audio_path: Path,
    script_text: str,
    model_size: str = "tiny",
    sync_offset_sec: float = 0.06,
) -> Optional[List[WordEntry]]:
    """
    Transcribe audio with word timestamps and align to the known script.
    Returns None if faster-whisper is not installed or transcription fails.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    script_words = script_text.split()
    if not script_words:
        return None

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
            vad_filter=False,
            condition_on_previous_text=False,
        )

        whisper_words: List[Tuple[float, float, str]] = []
        for segment in segments:
            if not segment.words:
                continue
            for word_info in segment.words:
                token = (word_info.word or "").strip()
                if token:
                    whisper_words.append(
                        (word_info.start, word_info.end, token)
                    )

        if len(whisper_words) < max(len(script_words) // 3, 3):
            return None

        aligned = _align_script_to_whisper(script_words, whisper_words)
        if sync_offset_sec:
            aligned = [
                (max(0.0, start - sync_offset_sec), max(0.0, end - sync_offset_sec), word)
                for start, end, word in aligned
            ]
        return aligned
    except Exception:
        return None
