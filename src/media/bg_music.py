"""
Optional background music mixing for Shorts with voice ducking.

Source order: local file on the volume, SHORTS_MUSIC_URL, the R2 bucket,
Pixabay CDN, then a synthesized pad. Pixabay answers 403 from datacenter IPs,
so Railway must not depend on it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import imageio_ffmpeg
import requests

from src.paths import ROOT, data_root

DEFAULT_BG_NAME = "background.mp3"
SYNTH_BG_NAME = "background_pad.mp3"
R2_MUSIC_KEY = "assets/background.mp3"
DOWNLOAD_URLS = (
    "https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/audio/2022/03/24/audio_2de51d759c.mp3",
    "https://cdn.pixabay.com/audio/2021/08/09/audio_dc39bde8b6.mp3",
)
_HEADERS = {"User-Agent": "CoinWire/1.0 (shorts bed)"}

# Am - F - C - G pad. Root / third / fifth per chord, 2.5s each.
_PAD_CHORDS = (
    (110.00, 261.63, 329.63),
    (87.31, 220.00, 261.63),
    (130.81, 329.63, 392.00),
    (98.00, 246.94, 293.66),
)
_PAD_CHORD_SEC = 2.5

SOURCE_NONE = "none"
SOURCE_SYNTH = "synth"


def _candidate_paths() -> list[Path]:
    return [
        data_root() / "assets" / DEFAULT_BG_NAME,
        ROOT / "data" / "assets" / DEFAULT_BG_NAME,
        Path(__file__).resolve().parent / "assets" / DEFAULT_BG_NAME,
        Path("data/assets") / DEFAULT_BG_NAME,
    ]


def _usable(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 10_000


def _env_urls() -> tuple[str, ...]:
    raw = os.getenv("SHORTS_MUSIC_URL", "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _download(url: str, dest: Path) -> bool:
    try:
        response = requests.get(url, timeout=60, headers=_HEADERS)
        response.raise_for_status()
        if len(response.content) < 10_000:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return True
    except requests.RequestException as exc:
        print(f"      Music download skipped ({url.split('/')[-1]}): {exc}")
        return False


def _pull_from_r2(dest: Path) -> bool:
    """Same bucket as B-roll / IG media host. Upload once, works forever."""

    def _get(*names: str) -> str:
        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    bucket = _get("BROLL_S3_BUCKET", "CROSSPOST_S3_BUCKET")
    access = _get("BROLL_S3_ACCESS_KEY", "CROSSPOST_S3_ACCESS_KEY")
    secret = _get("BROLL_S3_SECRET_KEY", "CROSSPOST_S3_SECRET_KEY")
    if not (bucket and access and secret):
        return False
    key = _get("SHORTS_MUSIC_KEY") or R2_MUSIC_KEY
    try:
        import boto3
        from botocore.client import Config

        kwargs = {
            "service_name": "s3",
            "aws_access_key_id": access,
            "aws_secret_access_key": secret,
            "region_name": _get("BROLL_S3_REGION", "CROSSPOST_S3_REGION") or "auto",
            "config": Config(signature_version="s3v4"),
        }
        endpoint = _get("BROLL_S3_ENDPOINT", "CROSSPOST_S3_ENDPOINT")
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        dest.parent.mkdir(parents=True, exist_ok=True)
        boto3.client(**kwargs).download_file(bucket, key, str(dest))
        return _usable(dest)
    except Exception as exc:
        print(f"      Music R2 pull skipped ({key}): {exc}")
        return False


def synth_music_bed(dest: Path | None = None) -> Path | None:
    """Soft four-chord pad built by ffmpeg — never fails on a blocked network."""
    target = Path(dest) if dest is not None else data_root() / "assets" / SYNTH_BG_NAME
    if _usable(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    inputs: list[str] = []
    chains: list[str] = []
    input_index = 0
    for chord_index, chord in enumerate(_PAD_CHORDS):
        labels: list[str] = []
        for freq in chord:
            labels.append(f"[{input_index}:a]")
            inputs.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={freq}:duration={_PAD_CHORD_SEC}:sample_rate=44100",
                ]
            )
            input_index += 1
        fade_out = round(_PAD_CHORD_SEC - 0.6, 2)
        chains.append(
            f"{''.join(labels)}amix=inputs={len(chord)}:duration=shortest,"
            f"afade=t=in:d=0.6,afade=t=out:st={fade_out}:d=0.6[c{chord_index}]"
        )
    concat_in = "".join(f"[c{index}]" for index in range(len(_PAD_CHORDS)))
    chains.append(
        f"{concat_in}concat=n={len(_PAD_CHORDS)}:v=0:a=1,"
        "lowpass=f=900,tremolo=f=0.25:d=0.25,volume=0.9[pad]"
    )
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                *inputs,
                "-filter_complex",
                ";".join(chains),
                "-map",
                "[pad]",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(target),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace")[-300:]
        print(f"      Music pad synth failed: {err}")
        return None
    if not _usable(target):
        return None
    print(f"      Music pad synthesized → {target}")
    return target


def resolve_background_music(*, allow_synth: bool = True) -> tuple[Path | None, str]:
    """Return (music file, source label) so the desk can flag a synth bed."""
    for path in _candidate_paths():
        if _usable(path):
            return path, "local"

    dest = data_root() / "assets" / DEFAULT_BG_NAME
    for url in _env_urls():
        if _download(url, dest):
            print(f"      Background music from SHORTS_MUSIC_URL → {dest}")
            return dest, "env_url"
    if _pull_from_r2(dest):
        print(f"      Background music pulled from R2 → {dest}")
        return dest, "r2"
    for url in DOWNLOAD_URLS:
        if _download(url, dest):
            print(f"      Background music downloaded → {dest}")
            return dest, "pixabay"

    if allow_synth and os.getenv("SHORTS_MUSIC_SYNTH", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }:
        pad = synth_music_bed()
        if pad:
            return pad, SOURCE_SYNTH
    print("      Background music missing: no local file, no URL, no R2")
    return None, SOURCE_NONE


def ensure_background_music(target: Path | None = None) -> Path | None:
    if target is not None:
        for path in _candidate_paths():
            if _usable(path):
                return path
        for url in (*_env_urls(), *DOWNLOAD_URLS):
            if _download(url, Path(target)):
                return Path(target)
        return None
    return resolve_background_music()[0]


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
