"""
Edge TTS audio generation with subtitles and natural pacing.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import edge_tts
import imageio_ffmpeg


DEFAULT_VOICE = "en-US-AndrewNeural"
DEFAULT_RATE = "-8%"
SENTENCE_PAUSE_SEC = 0.4
WORDS_PER_LINE = 4
BOUNDARY_TYPES = ("WordBoundary", "SentenceBoundary")


WordEntry = Tuple[float, float, str]


@dataclass
class TTSResult:
    audio_path: Path
    srt_path: Path
    ass_path: Path
    duration_estimate_sec: float
    sentences: List[str] = field(default_factory=list)
    sentence_durations: List[float] = field(default_factory=list)
    word_entries: List[WordEntry] = field(default_factory=list)


def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _srt_time_to_seconds(srt_time: str) -> float:
    time_part, millis = srt_time.split(",")
    h, m, s = time_part.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(millis) / 1000


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _expand_sentence_to_words(
    start_sec: float, end_sec: float, text: str
) -> List[Tuple[float, float, str]]:
    words = text.split()
    if not words:
        return []

    duration = max(end_sec - start_sec, 0.2)
    step = duration / len(words)
    return [
        (start_sec + index * step, start_sec + (index + 1) * step, word)
        for index, word in enumerate(words)
    ]


def _parse_srt_entries(srt_content: str) -> List[Tuple[float, float, str]]:
    entries: List[Tuple[float, float, str]] = []
    for block in srt_content.strip().split("\n\n"):
        parts = block.strip().split("\n")
        if len(parts) < 3 or " --> " not in parts[1]:
            continue
        start_raw, end_raw = parts[1].split(" --> ")
        text = " ".join(parts[2:]).strip()
        if not text:
            continue
        start = _srt_time_to_seconds(start_raw)
        end = _srt_time_to_seconds(end_raw)
        entries.extend(_expand_sentence_to_words(start, end, text))
    return entries


def build_word_entries_from_sentences(
    sentences: List[str],
    sentence_durations: List[float],
    pause_sec: float = SENTENCE_PAUSE_SEC,
) -> List[WordEntry]:
    """Word timings from probed per-sentence audio — matches voiceover exactly."""
    entries: List[WordEntry] = []
    timeline = 0.0

    for index, (sentence, duration) in enumerate(zip(sentences, sentence_durations)):
        words = sentence.split()
        if words:
            word_dur = duration / len(words)
            for word_index, word in enumerate(words):
                start = timeline + word_index * word_dur
                end = timeline + (word_index + 1) * word_dur
                entries.append((start, end, word))
        timeline += duration
        if index < len(sentences) - 1:
            timeline += pause_sec

    return entries


def extract_word_entries(srt_content: str) -> List[WordEntry]:
    """Expand SRT sentence boundaries into per-word timing entries."""
    return _parse_srt_entries(srt_content)


def _shift_srt(srt_content: str, offset_sec: float, index_start: int) -> tuple[str, int, float]:
    blocks = srt_content.strip().split("\n\n")
    shifted: List[str] = []
    last_end = 0.0
    idx = index_start

    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) < 3:
            continue
        start_raw, end_raw = parts[1].split(" --> ")
        start = _srt_time_to_seconds(start_raw) + offset_sec
        end = _srt_time_to_seconds(end_raw) + offset_sec
        last_end = max(last_end, end)
        text = " ".join(parts[2:]).strip()
        shifted.append(
            f"{idx}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{text}"
        )
        idx += 1

    return "\n\n".join(shifted), idx, last_end


async def _generate_sentence(
    sentence: str,
    voice: str,
    rate: str,
    output_path: Path,
    pitch: str = "+0Hz",
) -> tuple[Path, str, float]:
    communicate = edge_tts.Communicate(sentence, voice, rate=rate, pitch=pitch)
    submaker = edge_tts.SubMaker()

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in BOUNDARY_TYPES:
                submaker.feed(chunk)

    srt = submaker.get_srt()
    duration = _probe_audio_duration(output_path)
    return output_path, srt, duration


def _probe_audio_duration(path: Path) -> float:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            raw = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = raw.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 3.0


def _create_silence(output_path: Path, duration_sec: float) -> Path:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            str(duration_sec),
            "-q:a",
            "9",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def _concat_audio(parts: List[Path], output_path: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    list_path = output_path.with_suffix(".txt")
    lines = [f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in parts]
    list_path.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    list_path.unlink(missing_ok=True)


async def _generate_async(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    audio_path: Path,
    srt_path: Path,
    ass_path: Path,
    work_dir: Path,
) -> tuple[float, List[str], List[float], str]:
    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text.strip()]

    work_dir.mkdir(parents=True, exist_ok=True)
    silence_path = work_dir / "pause.mp3"
    _create_silence(silence_path, SENTENCE_PAUSE_SEC)

    audio_parts: List[Path] = []
    srt_blocks: List[str] = []
    sentence_durations: List[float] = []
    offset = 0.0
    srt_index = 1

    for index, sentence in enumerate(sentences):
        part_path = work_dir / f"sentence_{index:02d}.mp3"
        _, srt_part, duration = await _generate_sentence(
            sentence, voice, rate, part_path, pitch=pitch
        )
        sentence_durations.append(duration)

        if srt_part.strip():
            shifted, srt_index, last_end = _shift_srt(srt_part, offset, srt_index)
            srt_blocks.append(shifted)
            offset = last_end
        else:
            offset += duration

        audio_parts.append(part_path)
        if index < len(sentences) - 1:
            audio_parts.append(silence_path)
            offset += SENTENCE_PAUSE_SEC

    _concat_audio(audio_parts, audio_path)

    srt_content = "\n\n".join(srt_blocks)
    srt_path.write_text(srt_content, encoding="utf-8")

    return _probe_audio_duration(audio_path), sentences, sentence_durations, srt_content


def generate_voiceover(
    text: str,
    output_dir: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    basename: str = "voiceover",
    pitch: str = "+0Hz",
) -> TTSResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{basename}.mp3"
    srt_path = output_dir / f"{basename}.srt"
    ass_path = output_dir / f"{basename}.ass"

    duration, sentences, sentence_durations, srt_content = asyncio.run(
        _generate_async(
            text,
            voice,
            rate,
            pitch,
            audio_path,
            srt_path,
            ass_path,
            output_dir / "tts_parts",
        )
    )

    word_entries = extract_word_entries(srt_content)
    if not word_entries:
        word_entries = build_word_entries_from_sentences(sentences, sentence_durations)

    return TTSResult(
        audio_path=audio_path,
        srt_path=srt_path,
        ass_path=ass_path,
        duration_estimate_sec=duration,
        sentences=sentences,
        sentence_durations=sentence_durations,
        word_entries=word_entries,
    )
