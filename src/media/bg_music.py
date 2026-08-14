"""
Optional background music mixing for Shorts with voice ducking.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
import requests

from src.paths import ROOT, data_root

DEFAULT_BG_NAME = "background.mp3"
DOWNLOAD_URLS = (
    "https://cdn.pixabay.com/audio/2022/03/24/audio_2de51d759c.mp3",
    "https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/audio/2021/08/09/audio_dc39bde8b6.mp3",
)
_HEADERS = {"User-Agent": "CoinWire/1.0 (shorts bed)"}


def _candidate_paths() -> list[Path]:
    return [
        data_root() / "assets" / DEFAULT_BG_NAME,
        ROOT / "data" / "assets" / DEFAULT_BG_NAME,
        Path(__file__).resolve().parent / "assets" / DEFAULT_BG_NAME,
        Path("data/assets") / DEFAULT_BG_NAME,
    ]


def _usable(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 10_000


def ensure_background_music(target: Path | None = None) -> Path | None:
    for path in _candidate_paths():
        if _usable(path):
            return path

    dest = Path(target) if target is not None else data_root() / "assets" / DEFAULT_BG_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    for url in DOWNLOAD_URLS:
        try:
            response = requests.get(url, timeout=60, headers=_HEADERS)
            response.raise_for_status()
            if len(response.content) < 10_000:
                continue
            dest.write_bytes(response.content)
            print(f"      Background music downloaded → {dest}")
            return dest
        except requests.RequestException as exc:
            print(f"      Background music download skipped ({url.split('/')[-1]}): {exc}")
    print("      Background music missing: no local file and download failed")
    return None


def mix_background_music(
    voice_path: Path,
    output_path: Path,
    music_path: Path | None = None,
    music_volume: float = 0.10,
) -> Path:
    """Sidechain ducking: music drops when voice speaks."""
    music_path = music_path or ensure_background_music()
    if not music_path or not _usable(music_path):
        return voice_path

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    filter_graph = (
        f"[1:a]volume={music_volume},aloop=loop=-1:size=2e+09[bg];"
        f"[0:a]asplit=2[voice][sc];"
        f"[bg][sc]sidechaincompress="
        f"threshold=0.015:ratio=8:attack=50:release=500:level_sc=1[ducked];"
        f"[voice][ducked]amix=inputs=2:duration=first:weights=1 0.35[aout]"
    )
    try:
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
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace")[-400:]
        print(f"      Background music mix failed, voice only: {err}")
        return voice_path
    return output_path
