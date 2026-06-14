"""

FFmpeg-based renderer for 9:16 YouTube Shorts.

Fast-cut B-roll + hook stat + karaoke subtitles + brand watermark.

"""



from __future__ import annotations



import json

import shutil

import re
import subprocess

from pathlib import Path

from typing import List, Optional



import imageio_ffmpeg

from PIL import Image, ImageDraw, ImageFont



from src.media.bg_music import mix_background_music
from src.media.chart_fallback import create_chart_card_video
from src.media.edge_tts_audio import TTSResult, generate_voiceover
from src.media.karaoke_ass import build_karaoke_ass
from src.media.script_parser import extract_outro_summary, extract_stat_overlays, plan_broll_segments
from src.media.sfx_mixer import mix_sfx, plan_sfx_events
from src.media.stock_image_fetcher import StockImageFetcher
from src.media.stock_video_fetcher import StockVideoFetcher

from src.media.text_overlay import apply_final_layers, create_outro_png
from src.media.thumbnail_generator import create_short_thumbnail, create_vertical_cover

from src.media.video_encode import (
    AUDIO_ENCODE_ARGS,
    FINAL_ENCODE_ARGS,
    INTERMEDIATE_ENCODE_ARGS,
)

from src.media.whisper_timestamps import refine_word_timestamps





SHORT_WIDTH = 1080

SHORT_HEIGHT = 1920

FPS = 30

TRANSITION_SEC = 0.25
HOOK_INTRO_SEC = 2.5
OUTRO_DURATION_SEC = 3.0

SCALE_CROP_FILTER = (
    f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
    f"crop={SHORT_WIDTH}:{SHORT_HEIGHT},setsar=1"
)


def probe_video_size(path: Path) -> tuple[int, int]:
    """Return (width, height) of a video file."""
    ffmpeg = get_ffmpeg()
    result = subprocess.run(
        [ffmpeg, "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in result.stderr.splitlines():
        if "Video:" in line and "," in line:
            # e.g. 1080x1920
            match = re.search(r"(\d{3,4})x(\d{3,4})", line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return 0, 0


def _image_to_clip(
    image_path: Path,
    output: Path,
    duration_sec: float,
) -> None:
    """Turn a hi-res photo into a sharp 1080x1920 clip."""
    ffmpeg = get_ffmpeg()
    vf = (
        f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={SHORT_WIDTH}:{SHORT_HEIGHT},setsar=1,format=yuv420p"
    )
    _run([
        ffmpeg, "-y", "-loop", "1", "-i", str(image_path),
        "-t", str(duration_sec), "-vf", vf,
        *INTERMEDIATE_ENCODE_ARGS, "-r", str(FPS), "-an", str(output),
    ])


def get_ffmpeg() -> str:

    return imageio_ffmpeg.get_ffmpeg_exe()





def _run(cmd: List[str], cwd: Optional[Path] = None) -> None:

    result = subprocess.run(

        cmd,

        capture_output=True,

        text=True,

        encoding="utf-8",

        errors="replace",

        cwd=str(cwd) if cwd else None,

    )

    if result.returncode != 0:

        raise RuntimeError(

            f"FFmpeg failed:\nCMD: {' '.join(cmd)}\nSTDERR: {result.stderr}"

        )





def probe_duration(path: Path) -> float:

    ffmpeg = get_ffmpeg()

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

    raise RuntimeError(f"Could not read duration for {path}")





GRADIENT_PALETTES = [

    ((10, 14, 26), (0, 90, 70)),

    ((18, 22, 38), (120, 40, 180)),

    ((8, 20, 35), (200, 120, 20)),

    ((12, 16, 28), (30, 100, 200)),

]





def _create_gradient_card(

    label: str,

    output_path: Path,

    duration_sec: float,

    palette_index: int = 0,

) -> Path:

    top, bottom = GRADIENT_PALETTES[palette_index % len(GRADIENT_PALETTES)]

    image = Image.new("RGB", (SHORT_WIDTH, SHORT_HEIGHT))

    draw = ImageDraw.Draw(image)



    for y in range(SHORT_HEIGHT):

        ratio = y / SHORT_HEIGHT

        color = tuple(

            int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)

        )

        draw.line([(0, y), (SHORT_WIDTH, y)], fill=color)



    try:

        font_large = ImageFont.truetype("arialbd.ttf", 56)

        font_small = ImageFont.truetype("arial.ttf", 32)

    except OSError:

        font_large = ImageFont.load_default()

        font_small = ImageFont.load_default()



    draw.text((70, 120), "COIN WIRE", fill=(0, 220, 150), font=font_small)

    words = label.split()

    lines: List[str] = []

    current: List[str] = []

    for word in words:

        current.append(word)

        if len(" ".join(current)) > 16:

            lines.append(" ".join(current[:-1]))

            current = [word]

    if current:

        lines.append(" ".join(current))



    y = 820

    for line in lines[:3]:

        draw.text((70, y), line, fill=(255, 255, 255), font=font_large)

        y += 72



    png_path = output_path.with_suffix(".png")

    image.save(png_path)



    ffmpeg = get_ffmpeg()

    _run([

        ffmpeg, "-y", "-loop", "1", "-i", str(png_path),

        "-t", str(duration_sec),

        "-vf", f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:flags=lanczos,format=yuv420p",
        "-r", str(FPS), "-an",
        *INTERMEDIATE_ENCODE_ARGS,
        str(output_path),
    ])
    return output_path


def _append_silence(
    audio_path: Path,
    silence_sec: float,
    output_path: Path,
) -> Path:
    ffmpeg = get_ffmpeg()
    _run([
        ffmpeg, "-y",
        "-i", str(audio_path),
        "-f", "lavfi", "-t", str(silence_sec),
        "-i", "anullsrc=r=24000:cl=mono",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_path),
    ])
    return output_path


def _create_outro_clip(
    output_path: Path,
    duration_sec: float = OUTRO_DURATION_SEC,
    summary: str = "",
) -> Path:
    png_path = output_path.with_suffix(".png")
    create_outro_png(png_path, summary=summary)
    ffmpeg = get_ffmpeg()
    _run([
        ffmpeg, "-y", "-loop", "1", "-i", str(png_path),
        "-t", str(duration_sec),
        "-vf", f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:flags=lanczos,format=yuv420p",
        "-r", str(FPS), "-an",
        *INTERMEDIATE_ENCODE_ARGS,
        str(output_path),
    ])
    return output_path


def _create_hook_intro_clip(
    title: str,
    output_path: Path,
    duration_sec: float = 2.5,
) -> Path:
    """Sharp branded opener — avoids blurry stock as first frame."""
    png_path = output_path.with_suffix(".png")
    create_vertical_cover(title, png_path)
    ffmpeg = get_ffmpeg()
    _run([
        ffmpeg, "-y", "-loop", "1", "-i", str(png_path),
        "-t", str(duration_sec),
        "-vf", f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:flags=lanczos,format=yuv420p",
        "-r", str(FPS), "-an",
        *INTERMEDIATE_ENCODE_ARGS,
        str(output_path),
    ])
    return output_path


def _normalize_clip(
    source: Path,
    output: Path,
    duration_sec: float,
    clip_index: int = 0,
) -> None:
    """Scale and crop stock footage — no zoompan (causes shake/static on loop)."""
    ffmpeg = get_ffmpeg()
    vf = f"{SCALE_CROP_FILTER},format=yuv420p"
    encode = [*INTERMEDIATE_ENCODE_ARGS, "-r", str(FPS), "-an"]
    _run([
        ffmpeg, "-y", "-stream_loop", "-1", "-i", str(source),
        "-t", str(duration_sec), "-vf", vf,
        *encode, str(output),
    ])

    # zoompan can produce tiny frozen files — reject and retry simpler path
    if output.exists() and output.stat().st_size < 80_000:
        _run([
            ffmpeg, "-y", "-i", str(source),
            "-t", str(duration_sec), "-vf", vf,
            *encode, str(output),
        ])





def _concat_hard(clips: List[Path], output: Path) -> None:
    """Join clips without transition — clean cut for outro card."""
    if len(clips) == 1:
        _run([get_ffmpeg(), "-y", "-i", str(clips[0]), "-c", "copy", str(output)])
        return

    list_path = output.with_suffix(".concat.txt")
    lines = [f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in clips]
    list_path.write_text("\n".join(lines), encoding="utf-8")
    _run([
        get_ffmpeg(), "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_path), "-c", "copy", str(output),
    ])
    list_path.unlink(missing_ok=True)


def _xfade_clips(

    clips: List[Path],

    output: Path,

    transition_sec: float = TRANSITION_SEC,

) -> None:

    if len(clips) == 1:

        _run([get_ffmpeg(), "-y", "-i", str(clips[0]), "-c", "copy", str(output)])

        return



    durations = [probe_duration(clip) for clip in clips]

    fade_types = ["fade", "slideleft", "slideright", "fadeblack", "wiperight"]

    inputs: List[str] = []

    for clip in clips:

        inputs.extend(["-i", str(clip)])



    filter_parts: List[str] = []

    prev_label = "0:v"

    cumulative = durations[0]



    for index in range(1, len(clips)):

        out_label = "vout" if index == len(clips) - 1 else f"vx{index}"

        offset = max(cumulative - transition_sec, 0.1)

        transition = fade_types[index % len(fade_types)]

        filter_parts.append(

            f"[{prev_label}][{index}:v]xfade=transition={transition}:"

            f"duration={transition_sec}:offset={offset:.3f}[{out_label}]"

        )

        prev_label = out_label

        cumulative += durations[index] - transition_sec



    _run([

        get_ffmpeg(), "-y", *inputs,

        "-filter_complex", ";".join(filter_parts),

        "-map", f"[{prev_label}]",

        *INTERMEDIATE_ENCODE_ARGS, "-r", str(FPS), "-an", str(output),

    ])





def _pad_video_to_duration(

    video_path: Path,

    target_duration: float,

    output_path: Path,

) -> None:

    current = probe_duration(video_path)

    pad_sec = max(target_duration - current, 0)

    if pad_sec < 0.05:

        shutil.copy2(video_path, output_path)

        return



    _run([

        get_ffmpeg(), "-y", "-i", str(video_path),

        "-vf", f"tpad=stop_mode=clone:stop_duration={pad_sec:.3f}",

        "-t", f"{target_duration:.3f}", "-an", str(output_path),

    ])





def _merge_audio_video(

    video_path: Path,

    audio_path: Path,

    output_path: Path,

) -> None:

    audio_duration = probe_duration(audio_path)

    video_duration = probe_duration(video_path)



    working_video = video_path

    if video_duration > audio_duration + 0.15:
        trimmed = video_path.with_name(f"{video_path.stem}_trimmed.mp4")
        print(f"      Trimming video {video_duration:.1f}s -> {audio_duration:.1f}s")
        _run([
            get_ffmpeg(), "-y", "-i", str(video_path),
            "-t", f"{audio_duration:.3f}", "-c", "copy", str(trimmed),
        ])
        working_video = trimmed
    elif video_duration < audio_duration - 0.1:

        padded = video_path.with_name(f"{video_path.stem}_padded.mp4")

        print(f"      Padding video {video_duration:.1f}s -> {audio_duration:.1f}s")

        _pad_video_to_duration(video_path, audio_duration, padded)

        working_video = padded



    _run([

        get_ffmpeg(), "-y",

        "-i", str(working_video), "-i", str(audio_path),

        "-map", "0:v:0", "-map", "1:a:0",

        "-c:v", "copy",

        *AUDIO_ENCODE_ARGS,

        "-t", f"{audio_duration:.3f}", str(output_path),

    ])





def _burn_karaoke_ass(
    video_path: Path,
    ass_path: Path,
    output_path: Path,
    work_dir: Path,
) -> Path:
    local_ass = work_dir / "burn_subs.ass"
    local_ass.write_text(ass_path.read_text(encoding="utf-8"), encoding="utf-8")

    video_in_work = work_dir / video_path.name
    if video_path.resolve() != video_in_work.resolve():
        shutil.copy2(video_path, video_in_work)

    local_out = work_dir / "final_short.mp4"
    _run([
        get_ffmpeg(), "-y", "-i", video_in_work.name,
        "-vf", "ass=burn_subs.ass",
        *FINAL_ENCODE_ARGS,
        "-c:a", "copy", local_out.name,
    ], cwd=work_dir)

    if local_out.resolve() == output_path.resolve():
        return output_path

    try:
        shutil.copy2(local_out, output_path)
        return output_path
    except PermissionError:
        fallback = output_path.with_name(f"{output_path.stem}_new{output_path.suffix}")
        shutil.copy2(local_out, fallback)
        print(
            f"      WARNING: {output_path.name} is locked (close video player). "
            f"Saved to: {fallback}"
        )
        return fallback





def _fetch_broll_clips(

    fetcher: StockVideoFetcher,

    segments: List[dict],

    work_dir: Path,

    visual_mode: str = "mixed",

    min_stock_height: int = 1920,

    image_fetcher: Optional[StockImageFetcher] = None,

) -> List[Path]:

    raw_dir = work_dir / "raw"

    raw_dir.mkdir(parents=True, exist_ok=True)

    clips: List[Path] = []

    prefer_hd = visual_mode == "mixed"
    min_fetch_height = 1920 if prefer_hd else 1080

    for index, segment in enumerate(segments):

        keyword = segment["keyword"]

        duration = segment["duration"]

        # 1) Stock photos — only when explicitly requested
        if visual_mode in ("mixed", "stock_image", "image") and image_fetcher:
            raw_path = raw_dir / f"seg_{index:02d}.jpg"
            image_meta = image_fetcher.fetch_image_for_keyword(keyword)
            if image_meta:
                downloaded = image_fetcher.download_image(image_meta, raw_path)
                if downloaded:
                    clip_path = work_dir / f"photo_{index:02d}.mp4"
                    _image_to_clip(downloaded, clip_path, duration)
                    clips.append(clip_path)
                    print(
                        f"      [{index + 1}/{len(segments)}] {keyword} ({duration:.1f}s)"
                        f" — photo {image_meta['source']}"
                        f" {image_meta.get('width', '?')}x{image_meta.get('height', '?')}"
                    )
                    continue

        # 2) Stock video (primary for stock_video mode)
        use_stock_video = visual_mode in ("stock", "stock_video", "mixed")
        if use_stock_video:
            video_meta = fetcher.fetch_video_for_keyword(
                keyword, min_height=min_fetch_height
            )
            if video_meta and prefer_hd and video_meta.get("height", 0) < min_stock_height:
                video_meta = None

            if video_meta:
                video_raw = raw_dir / f"seg_{index:02d}.mp4"
                downloaded = fetcher.download_video(video_meta, video_raw)
                if downloaded:
                    w, h = probe_video_size(downloaded)
                    if h >= min_stock_height or visual_mode in ("stock", "stock_video"):
                        norm = work_dir / f"norm_{index:02d}.mp4"
                        _normalize_clip(downloaded, norm, duration, clip_index=index)
                        clips.append(norm)
                        print(
                            f"      [{index + 1}/{len(segments)}] {keyword} ({duration:.1f}s)"
                            f" — video {w}x{h}"
                        )
                        continue
                    print(f"      [{index + 1}/{len(segments)}] video {w}x{h} too small")

        # 3) Chart fallback
        fallback = work_dir / f"chart_{index:02d}.mp4"
        create_chart_card_video(keyword, fallback, duration)
        clips.append(fallback)
        print(f"      [{index + 1}/{len(segments)}] {keyword} — sharp chart ({duration:.1f}s)")



    return clips





class FFmpegShortRenderer:

    def __init__(

        self,

        pexels_api_key: Optional[str] = None,

        pixabay_api_key: Optional[str] = None,

        visual_mode: str = "mixed",

    ):

        self.video_fetcher = StockVideoFetcher(

            pexels_api_key=pexels_api_key,

            pixabay_api_key=pixabay_api_key,

        )
        self.image_fetcher = StockImageFetcher(
            pexels_api_key=pexels_api_key,
            pixabay_api_key=pixabay_api_key,
        )
        self.visual_mode = visual_mode



    def render(

        self,

        script: str,

        title: str,

        output_path: Path,

        keywords: Optional[List[str]] = None,

        voice: str = "en-US-AndrewNeural",

        rate: str = "+5%",
        pitch: str = "-2Hz",

        work_dir: Optional[Path] = None,

        use_whisper: bool = False,

    ) -> Path:

        output_path.parent.mkdir(parents=True, exist_ok=True)

        work_dir = work_dir or output_path.parent / "renders" / "latest"

        work_dir.mkdir(parents=True, exist_ok=True)



        print("[1/7] Generating voiceover (edge-tts)...")

        tts: TTSResult = generate_voiceover(
            script, work_dir, voice=voice, rate=rate, pitch=pitch
        )

        audio_duration = probe_duration(tts.audio_path)

        print(f"      Audio: {tts.audio_path} ({audio_duration:.1f}s)")



        print("[2/7] Building word timestamps...")
        word_entries = list(tts.word_entries)
        if use_whisper:
            refined = refine_word_timestamps(
                tts.audio_path, script, sync_offset_sec=0.0
            )
            if refined:
                word_entries = refined
                print(f"      Whisper aligned: {len(word_entries)} words")
            else:
                print(f"      TTS sentence timings: {len(word_entries)} words")
        else:
            print(f"      TTS sentence timings: {len(word_entries)} words")



        ass_content = build_karaoke_ass(word_entries, time_offset_sec=0.0)

        tts.ass_path.write_text(ass_content, encoding="utf-8")



        print("[3/7] Planning fast-cut B-roll (1.5–2s)...")

        sentences = tts.sentences or [script]

        durations = tts.sentence_durations or [audio_duration / max(len(sentences), 1)]

        segments = plan_broll_segments(sentences, durations)



        planned_body = sum(s["duration"] for s in segments)

        # hook + body xfade: HOOK + sum(body) - n*TRANS == audio_duration
        body_target_sum = max(
            audio_duration - HOOK_INTRO_SEC + len(segments) * TRANSITION_SEC,
            3.0,
        )
        scale = body_target_sum / max(planned_body, 0.1)

        if abs(scale - 1.0) > 0.03:

            print(
                f"      Scaling clip durations x{scale:.2f} "
                f"(body fits after {HOOK_INTRO_SEC}s hook)"
            )

            for segment in segments:

                segment["duration"] = round(segment["duration"] * scale, 2)



        print(f"      {len(segments)} fast cuts from {len(sentences)} sentences")



        print("[4/7] Fetching stock videos...")
        self.video_fetcher.reset_used()
        self.image_fetcher.reset_used()
        raw_dir = work_dir / "raw"
        for old in work_dir.glob("norm_*.mp4"):
            old.unlink(missing_ok=True)
        for old in work_dir.glob("photo_*.mp4"):
            old.unlink(missing_ok=True)
        for old in raw_dir.glob("seg_*"):
            old.unlink(missing_ok=True)
        body_clips = _fetch_broll_clips(
            self.video_fetcher,
            segments,
            work_dir,
            visual_mode=self.visual_mode,
            image_fetcher=self.image_fetcher,
        )

        hook_clip = work_dir / "hook_intro.mp4"
        _create_hook_intro_clip(title, hook_clip, duration_sec=HOOK_INTRO_SEC)
        print(f"      Hook: sharp branded intro ({HOOK_INTRO_SEC}s)")



        print("[5/7] Concatenating + outro...")
        concat_path = work_dir / "concat.mp4"
        _xfade_clips([hook_clip, *body_clips], concat_path, transition_sec=TRANSITION_SEC)

        outro_clip = work_dir / "outro.mp4"
        outro_summary = extract_outro_summary(script)
        _create_outro_clip(outro_clip, duration_sec=OUTRO_DURATION_SEC, summary=outro_summary)
        print(f"      Outro: {outro_summary[:50]}...")
        concat_final = work_dir / "concat_with_outro.mp4"
        _concat_hard([concat_path, outro_clip], concat_final)



        print("[6/7] Mixing audio + brand overlays...")

        stat_overlays = extract_stat_overlays(script)

        audio_extended = work_dir / "voiceover_extended.mp3"
        _append_silence(tts.audio_path, OUTRO_DURATION_SEC, audio_extended)

        mixed_audio = work_dir / "voiceover_mixed.mp3"

        mixed_path = mix_background_music(audio_extended, mixed_audio)

        if mixed_path != audio_extended:

            print("      Background music added (ducked under voice)")

        else:

            print("      No background music (place data/assets/background.mp3)")

        segment_durs = [s["duration"] for s in segments]
        sfx_events = plan_sfx_events(
            segment_durs,
            TRANSITION_SEC,
            audio_duration,
            hook_ding=bool(stat_overlays),
            outro_sec=OUTRO_DURATION_SEC,
        )
        final_audio = work_dir / "voiceover_final.mp3"
        mix_sfx(mixed_path, final_audio, sfx_events, work_dir)
        if sfx_events:
            print(f"      SFX: {len(sfx_events)} hits (ding/whoosh/thud)")
        mixed_path = final_audio



        with_audio = work_dir / "with_audio.mp4"

        _merge_audio_video(concat_final, mixed_path, with_audio)

        if stat_overlays:

            print(f"      Stats: {[o.text for o in stat_overlays]}")

        print("[7/7] Brand + subtitles (single export)...")

        if "Dialogue:" not in ass_content:

            raise RuntimeError("Karaoke ASS has no dialogue events")

        final_path = apply_final_layers(
            with_audio,
            tts.ass_path,
            stat_overlays,
            word_entries,
            output_path,
            work_dir,
        )

        thumb_path = work_dir / "thumbnail.jpg"
        create_short_thumbnail(title, thumb_path)
        print(f"      Thumbnail: {thumb_path}")

        metadata = {

            "title": title,

            "duration_sec": probe_duration(final_path),

            "output": str(final_path),

            "thumbnail": str(thumb_path),

            "voice": voice,

            "sentences": len(sentences),

            "broll_segments": len(segments),

            "stat_overlays": [o.text for o in stat_overlays],

            "whisper": use_whisper and len(word_entries) > 0,

            "hook_from_start": True,
            "outro_sec": OUTRO_DURATION_SEC,

        }

        (work_dir / "metadata.json").write_text(

            json.dumps(metadata, indent=2), encoding="utf-8",

        )



        print(f"Done: {final_path}")

        return final_path


