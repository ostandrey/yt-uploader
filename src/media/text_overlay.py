"""
On-screen stat overlays, hook graphics, and persistent brand watermark.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from src.media.script_parser import StatOverlay

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
BRAND_COLOR = (0, 220, 150)
STAT_FADE_SEC = 0.35
STAT_SLIDE_PX = 28


def _stat_overlay_y(start: float, fade: float) -> str:
    """Slide-in y position — FFmpeg expressions have no int(), use float math."""
    return (
        f"if(lt(t-{start:.3f},{fade:.3f}),"
        f"-{STAT_SLIDE_PX}*(1-(t-{start:.3f})/{fade:.3f}),0)"
    )


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("arialbd.ttf", "Arial Bold.ttf", "arialblk.ttf")
        if bold
        else ("arial.ttf",)
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_stat_overlay_png(
    text: str,
    output_path: Path,
    accent: tuple[int, int, int] = BRAND_COLOR,
    hook_style: bool = False,
) -> Path:
    """Branded stat card for upper-third — bold hook variant at t=0."""
    image = Image.new("RGBA", (SHORT_WIDTH, SHORT_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_large = _load_font(110 if hook_style else 96)
    font_small = _load_font(32, bold=False)

    bbox = draw.textbbox((0, 0), text, font=font_large)
    text_w = bbox[2] - bbox[0]
    pad_x, pad_y = 44, 28
    box_w = text_w + pad_x * 2
    box_h = (bbox[3] - bbox[1]) + pad_y * 2
    box_x = (SHORT_WIDTH - box_w) // 2
    box_y = 120 if hook_style else 140

    if hook_style:
        draw.rounded_rectangle(
            [(box_x - 6, box_y - 6), (box_x + box_w + 6, box_y + box_h + 6)],
            radius=20,
            outline=(*accent, 180),
            width=3,
        )

    draw.rounded_rectangle(
        [(box_x, box_y), (box_x + box_w, box_y + box_h)],
        radius=16,
        fill=(8, 12, 22, 230),
        outline=(*accent, 255),
        width=4,
    )
    draw.text(
        (box_x + pad_x, box_y + pad_y - bbox[1]),
        text,
        fill=(255, 255, 255, 255),
        font=font_large,
    )
    draw.text(
        (box_x + pad_x, box_y + box_h + 10),
        "COIN WIRE",
        fill=(*accent, 220),
        font=font_small,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def create_hook_flash_png(output_path: Path) -> Path:
    """Red border flash for first 0.5s — pattern interrupt hook."""
    image = Image.new("RGBA", (SHORT_WIDTH, SHORT_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    border = 18
    draw.rectangle(
        [(0, 0), (SHORT_WIDTH, SHORT_HEIGHT)],
        outline=(255, 40, 40, 220),
        width=border,
    )
    draw.rectangle(
        [(border, border), (SHORT_WIDTH - border, SHORT_HEIGHT - border)],
        outline=(255, 80, 80, 120),
        width=6,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def create_outro_png(output_path: Path, summary: str = "") -> Path:
    """Branded CTA card for end of Short."""
    image = Image.new("RGBA", (SHORT_WIDTH, SHORT_HEIGHT), (8, 10, 18, 255))
    draw = ImageDraw.Draw(image)

    for y in range(SHORT_HEIGHT):
        ratio = y / SHORT_HEIGHT
        color = (int(8 + 15 * ratio), int(10 + 20 * ratio), int(18 + 30 * ratio), 255)
        draw.line([(0, y), (SHORT_WIDTH, y)], fill=color)

    font_brand = _load_font(80)
    font_summary = _load_font(34, bold=False)
    font_cta = _load_font(44)
    font_handle = _load_font(34, bold=False)

    brand = "COIN WIRE"
    bb = draw.textbbox((0, 0), brand, font=font_brand)
    draw.text(
        ((SHORT_WIDTH - bb[2] + bb[0]) // 2, 680),
        brand,
        fill=(*BRAND_COLOR, 255),
        font=font_brand,
    )

    if summary:
        words = summary.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            current.append(word)
            if len(" ".join(current)) > 32:
                lines.append(" ".join(current[:-1]))
                current = [word]
        if current:
            lines.append(" ".join(current))
        y = 800
        for line in lines[:2]:
            lb = draw.textbbox((0, 0), line, font=font_summary)
            draw.text(
                ((SHORT_WIDTH - lb[2] + lb[0]) // 2, y),
                line,
                fill=(200, 210, 225, 255),
                font=font_summary,
            )
            y += 46

    cta = "Follow for the next shift"
    cb = draw.textbbox((0, 0), cta, font=font_cta)
    draw.text(
        ((SHORT_WIDTH - cb[2] + cb[0]) // 2, 900),
        cta,
        fill=(255, 255, 255, 255),
        font=font_cta,
    )

    handle = "@coinwirenews"
    hb = draw.textbbox((0, 0), handle, font=font_handle)
    draw.text(
        ((SHORT_WIDTH - hb[2] + hb[0]) // 2, 980),
        handle,
        fill=(*BRAND_COLOR, 255),
        font=font_handle,
    )

    draw.rectangle([(200, 1050), (SHORT_WIDTH - 200, 1058)], fill=(*BRAND_COLOR, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def create_watermark_png(output_path: Path) -> Path:
    """Small persistent top-left watermark."""
    image = Image.new("RGBA", (SHORT_WIDTH, SHORT_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_font(28)

    label = "COIN WIRE"
    bbox = draw.textbbox((0, 0), label, font=font)
    pad_x, pad_y = 14, 8
    box_w = (bbox[2] - bbox[0]) + pad_x * 2
    box_h = (bbox[3] - bbox[1]) + pad_y * 2
    x, y = 36, 36

    draw.rounded_rectangle(
        [(x, y), (x + box_w, y + box_h)],
        radius=8,
        fill=(8, 12, 22, 170),
        outline=(*BRAND_COLOR, 200),
        width=2,
    )
    draw.text(
        (x + pad_x, y + pad_y - bbox[1]),
        label,
        fill=(*BRAND_COLOR, 255),
        font=font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _probe_duration(path: Path) -> float:
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
    return 30.0


def _run_overlay(
    video_path: Path,
    output_path: Path,
    work_dir: Path,
    extra_inputs: List[Path],
    filter_parts: List[str],
    final_label: str,
    encode_args: Optional[List[str]] = None,
) -> Path:
    from src.media.video_encode import FINAL_ENCODE_ARGS

    work_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video_encode = encode_args or FINAL_ENCODE_ARGS

    video_in = work_dir / video_path.name
    if video_path.resolve() != video_in.resolve():
        shutil.copy2(video_path, video_in)

    inputs = ["-i", video_in.name]
    for extra in extra_inputs:
        inputs.extend(["-i", extra.name])

    local_out = work_dir / "overlay_out.mp4"
    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{final_label}]",
        "-map", "0:a?",
        *video_encode,
        "-c:a", "copy",
        local_out.name,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(work_dir),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Overlay failed: {result.stderr}")

    if local_out.resolve() != output_path.resolve():
        try:
            shutil.copy2(local_out, output_path)
        except PermissionError:
            fallback = output_path.with_name(f"{output_path.stem}_new{output_path.suffix}")
            shutil.copy2(local_out, fallback)
            return fallback
    return output_path


def apply_final_layers(
    video_path: Path,
    ass_path: Path,
    overlays: List[StatOverlay],
    word_entries: List[tuple[float, float, str]],
    output_path: Path,
    work_dir: Path,
) -> Path:
    """Watermark + stats + karaoke subs in a single high-quality export."""
    from src.media.video_encode import FINAL_ENCODE_ARGS

    work_dir.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(video_path)

    extra_inputs: List[Path] = []
    filter_parts: List[str] = []
    filter_parts.append("[0:v]scale=in_range=full:out_range=limited,format=yuv420p,setsar=1[vnorm]")
    prev = "vnorm"
    input_index = 1

    watermark_path = work_dir / "watermark.png"
    create_watermark_png(watermark_path)
    extra_inputs.append(watermark_path)
    filter_parts.append(f"[{prev}][{input_index}:v]overlay=0:0:format=auto[vwm]")
    prev = "vwm"
    input_index += 1

    for overlay in overlays:
        start = 0.0 if overlay.show_from_start else 0.3
        if not overlay.show_from_start:
            for ws, _, word in word_entries:
                if overlay.keyword in word.lower():
                    start = ws
                    break

        png_path = work_dir / f"stat_{overlay.text.replace(' ', '_').replace('%', 'pct')}.png"
        create_stat_overlay_png(
            overlay.text, png_path, hook_style=overlay.show_from_start
        )
        extra_inputs.append(png_path)

        fade = STAT_FADE_SEC
        disp = overlay.display_sec
        total = disp + fade
        end = min(start + total, duration)
        stat_label = f"stat{input_index}"
        out_label = f"v{input_index}"
        y_expr = _stat_overlay_y(start, fade)

        filter_parts.append(
            f"[{input_index}:v]format=rgba,loop=loop=-1:size=1,fps=30,"
            f"trim=duration={total:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fade:.3f}:alpha=1,"
            f"fade=t=out:st={disp:.3f}:d={fade:.3f}:alpha=1,"
            f"setpts=PTS+{start:.3f}/TB[{stat_label}]"
        )
        filter_parts.append(
            f"[{prev}][{stat_label}]overlay=x=0:y='{y_expr}':"
            f"enable='between(t,{start:.3f},{end:.3f})':format=auto[{out_label}]"
        )
        prev = out_label
        input_index += 1

    local_ass = work_dir / "burn_subs.ass"
    local_ass.write_text(ass_path.read_text(encoding="utf-8"), encoding="utf-8")
    filter_parts.append(f"[{prev}]ass=burn_subs.ass[vfinal]")

    return _run_overlay(
        video_path,
        output_path,
        work_dir,
        extra_inputs,
        filter_parts,
        "vfinal",
        encode_args=FINAL_ENCODE_ARGS,
    )


def apply_brand_layers(
    video_path: Path,
    overlays: List[StatOverlay],
    word_entries: List[tuple[float, float, str]],
    output_path: Path,
    work_dir: Path,
) -> Path:
    """Hook stat + persistent watermark."""
    work_dir.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(video_path)

    extra_inputs: List[Path] = []
    filter_parts: List[str] = []
    filter_parts.append("[0:v]scale=in_range=full:out_range=limited,format=yuv420p,setsar=1[vnorm]")
    prev = "vnorm"
    input_index = 1

    watermark_path = work_dir / "watermark.png"
    create_watermark_png(watermark_path)
    extra_inputs.append(watermark_path)
    filter_parts.append(f"[{prev}][{input_index}:v]overlay=0:0:format=auto[vwm]")
    prev = "vwm"
    input_index += 1

    for overlay in overlays:
        start = 0.0 if overlay.show_from_start else 0.3
        if not overlay.show_from_start:
            for ws, _, word in word_entries:
                if overlay.keyword in word.lower():
                    start = ws
                    break

        png_path = work_dir / f"stat_{overlay.text.replace(' ', '_').replace('%', 'pct')}.png"
        create_stat_overlay_png(
            overlay.text, png_path, hook_style=overlay.show_from_start
        )
        extra_inputs.append(png_path)

        fade = STAT_FADE_SEC
        disp = overlay.display_sec
        total = disp + fade
        end = min(start + total, duration)
        stat_label = f"stat{input_index}"
        out_label = f"v{input_index}"
        y_expr = _stat_overlay_y(start, fade)

        filter_parts.append(
            f"[{input_index}:v]format=rgba,loop=loop=-1:size=1,fps=30,"
            f"trim=duration={total:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fade:.3f}:alpha=1,"
            f"fade=t=out:st={disp:.3f}:d={fade:.3f}:alpha=1,"
            f"setpts=PTS+{start:.3f}/TB[{stat_label}]"
        )
        filter_parts.append(
            f"[{prev}][{stat_label}]overlay=x=0:y='{y_expr}':"
            f"enable='between(t,{start:.3f},{end:.3f})':format=auto[{out_label}]"
        )
        prev = out_label
        input_index += 1

    if not overlays:
        return _run_overlay(
            video_path, output_path, work_dir, extra_inputs, filter_parts, prev
        )

    return _run_overlay(
        video_path, output_path, work_dir, extra_inputs, filter_parts, prev
    )


# Backwards-compatible alias
def apply_stat_overlays(
    video_path: Path,
    overlays: List[StatOverlay],
    word_entries: List[tuple[float, float, str]],
    output_path: Path,
    work_dir: Path,
    time_offset_sec: float = 0.0,
) -> Path:
    return apply_brand_layers(
        video_path, overlays, word_entries, output_path, work_dir
    )
