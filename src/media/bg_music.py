"""
Optional background music mixing for Shorts with voice ducking.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
import requests

DEFAULT_BG_PATH = Path("data/assets/background.mp3")
DEFAULT_BG_URL = (
    "https://cdn.pixabay.com/audio/2022/03/24/"
    "audio_2de51d759c.mp3"
)


def ensure_background_music(target: Path = DEFAULT_BG_PATH) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 10_000:
        return target

    try:
        response = requests.get(DEFAULT_BG_URL, timeout=60)
        response.raise_for_status()
        target.write_bytes(response.content)
        return target
    except requests.RequestException:
        return None


def mix_background_music(
    voice_path: Path,
    output_path: Path,
    music_path: Path | None = None,
    music_volume: float = 0.10,
) -> Path:
    """Sidechain ducking: music drops when voice speaks."""
    music_path = music_path or ensure_background_music()
    if not music_path or not music_path.exists():
        return voice_path

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    filter_graph = (
        f"[1:a]volume={music_volume},aloop=loop=-1:size=2e+09[bg];"
        f"[0:a]asplit=2[voice][sc];"
        f"[bg][sc]sidechaincompress="
        f"threshold=0.015:ratio=8:attack=50:release=500:level_sc=1[ducked];"
        f"[voice][ducked]amix=inputs=2:duration=first:weights=1 0.35[aout]"
    )
    subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex", filter_graph,
            "-map", "[aout]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path
