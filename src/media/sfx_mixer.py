"""
Subtle news-style SFX: ding on stats, whoosh on cuts, thud on outro.
Generates tones via FFmpeg if asset files are missing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Tuple

import imageio_ffmpeg

ASSETS_DIR = Path("data/assets")
SFX_FILES = {
    "ding": ASSETS_DIR / "ding.mp3",
    "whoosh": ASSETS_DIR / "whoosh.mp3",
    "thud": ASSETS_DIR / "thud.mp3",
}

# lavfi recipes for procedural fallbacks
SFX_RECIPES = {
    "ding": ("sine=frequency=920:duration=0.14", "afade=t=out:st=0.05:d=0.09"),
    "whoosh": ("anoisesrc=d=0.12:color=pink:amplitude=0.25", "lowpass=f=600,afade=t=out:st=0:d=0.12"),
    "thud": ("sine=frequency=70:duration=0.22", "afade=t=out:st=0.08:d=0.14"),
}

SFX_VOLUME = {"ding": 0.35, "whoosh": 0.18, "thud": 0.28}


def _ensure_sfx(name: str, work_dir: Path) -> Path:
    asset = SFX_FILES[name]
    if asset.exists() and asset.stat().st_size > 500:
        return asset

    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"{name}_gen.mp3"
    if target.exists() and target.stat().st_size > 500:
        return target

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    lavfi_src, af_filter = SFX_RECIPES[name]
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", lavfi_src,
            "-af", af_filter,
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(target),
        ],
        check=True,
        capture_output=True,
    )
    return target


def plan_sfx_events(
    segment_durations: List[float],
    transition_sec: float,
    voice_duration: float,
    hook_ding: bool = True,
    outro_sec: float = 0.0,
) -> List[Tuple[float, str]]:
    """Return (timestamp_sec, sfx_name) pairs."""
    events: List[Tuple[float, str]] = []
    if hook_ding:
        events.append((0.08, "ding"))

    elapsed = 0.0
    for index, duration in enumerate(segment_durations):
        elapsed += duration
        if index < len(segment_durations) - 1:
            cut_time = max(elapsed - transition_sec, 0.15)
            events.append((cut_time, "whoosh"))

    # Thud when outro card appears (after voice ends), not during last word
    thud_at = voice_duration + 0.08 if outro_sec > 0 else max(voice_duration - 0.15, 0.5)
    events.append((thud_at, "thud"))
    return events


def mix_sfx(
    audio_path: Path,
    output_path: Path,
    events: List[Tuple[float, str]],
    work_dir: Path,
) -> Path:
    if not events:
        import shutil
        shutil.copy2(audio_path, output_path)
        return output_path

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs = ["-i", str(audio_path)]
    filter_parts: List[str] = []
    sfx_labels: List[str] = []

    for index, (time_sec, name) in enumerate(events):
        sfx_path = _ensure_sfx(name, work_dir)
        inputs.extend(["-i", str(sfx_path)])
        label = f"sfx{index}"
        delay_ms = int(time_sec * 1000)
        vol = SFX_VOLUME.get(name, 0.2)
        filter_parts.append(
            f"[{index + 1}:a]volume={vol},adelay={delay_ms}|{delay_ms}[{label}]"
        )
        sfx_labels.append(f"[{label}]")

    mix_inputs = "[0:a]" + "".join(sfx_labels)
    filter_parts.append(
        f"{mix_inputs}amix=inputs={1 + len(events)}:"
        f"duration=first:dropout_transition=0:normalize=0[aout]"
    )

    subprocess.run(
        [
            ffmpeg, "-y",
            *inputs,
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
