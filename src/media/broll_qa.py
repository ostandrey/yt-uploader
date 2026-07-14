"""
Visual QA for B-roll clips: ffprobe + optional YOLOv8 tagging.

YOLO only sees frames — never text posts.
If ultralytics is not installed, ffprobe still runs and YOLO is marked skipped.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio_ffmpeg

log = logging.getLogger(__name__)

# COCO class names we care about (ultralytics default order)
_SCREEN_CLASSES = {"laptop", "tv", "cell phone"}
_CROWD_CLASS = "person"
_OFFTOPIC = {
    "dog", "cat", "bird", "horse", "sheep", "cow",
    "sports ball", "frisbee", "bench", "pizza", "cake",
    "banana", "apple", "sandwich", "hot dog", "broccoli",
}


def probe_video(path: Path) -> Dict[str, Any]:
    """Return duration / size. Prefer OpenCV; fallback parse `ffmpeg -i`."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap.release()
            duration = (frames / fps) if fps > 0 else 0.0
            if width and height:
                return {
                    "duration_sec": duration,
                    "width": width,
                    "height": height,
                    "portrait": height >= width,
                }
    except Exception:  # noqa: BLE001
        pass

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        result = subprocess.run(
            [ffmpeg, "-i", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        err = result.stderr or ""
    except (OSError, subprocess.SubprocessError):
        return {}

    duration = 0.0
    width = height = 0
    # Duration: 00:00:12.34
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    # Stream #0:0: Video: ... 1080x1920
    m2 = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", err)
    if m2:
        width, height = int(m2.group(1)), int(m2.group(2))
    if not width and not duration:
        return {}
    return {
        "duration_sec": duration,
        "width": width,
        "height": height,
        "portrait": height >= width if width and height else False,
    }


def ffprobe_gate(
    probe: Dict[str, Any],
    *,
    min_duration: float = 5.0,
    max_duration: float = 30.0,
    min_edge: int = 720,
    prefer_portrait: bool = True,
) -> List[str]:
    """Return list of reject reasons (empty = pass tech gate)."""
    reasons: List[str] = []
    if not probe:
        return ["ffprobe_failed"]
    dur = float(probe.get("duration_sec") or 0)
    if dur < min_duration:
        reasons.append(f"too_short:{dur:.1f}s")
    if dur > max_duration:
        reasons.append(f"too_long:{dur:.1f}s")
    w = int(probe.get("width") or 0)
    h = int(probe.get("height") or 0)
    if min(w, h) < min_edge:
        reasons.append(f"low_res:{w}x{h}")
    if prefer_portrait and w and h and h < w and h < 1080:
        reasons.append("landscape_low_height")
    return reasons


def _sample_frame_paths(video: Path, work: Path, n: int = 5) -> List[Path]:
    """Extract n JPEG keyframes with ffmpeg."""
    work.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    probe = probe_video(video)
    duration = max(float(probe.get("duration_sec") or 5.0), 1.0)
    paths: List[Path] = []
    for i in range(n):
        t = duration * (i / max(n - 1, 1))
        out = work / f"frame_{i:02d}.jpg"
        cmd = [
            ffmpeg, "-y", "-ss", f"{t:.2f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(out),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, check=False)
            if out.exists() and out.stat().st_size > 1000:
                paths.append(out)
        except (OSError, subprocess.SubprocessError):
            continue
    return paths


def yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


_YOLO_MODEL = None


def _get_yolo():
    global _YOLO_MODEL
    if _YOLO_MODEL is not None:
        return _YOLO_MODEL
    from ultralytics import YOLO
    _YOLO_MODEL = YOLO("yolov8n.pt")
    return _YOLO_MODEL


def run_yolo_on_video(video: Path, work: Path) -> Dict[str, Any]:
    """
    Tag clip with YOLO signals. Returns dict with flags + counts.
    Raises ImportError if ultralytics missing.
    """
    model = _get_yolo()
    frames = _sample_frame_paths(video, work / "frames", n=5)
    if not frames:
        return {"yolo_error": "no_frames", "reject": True, "reject_reasons": ["no_frames"]}

    person_counts: List[int] = []
    screen_hits = 0
    offtopic_hits = 0
    labels_seen: List[str] = []

    for frame in frames:
        results = model.predict(str(frame), verbose=False)
        names = results[0].names if results else {}
        boxes = results[0].boxes if results else None
        persons = 0
        has_screen = False
        if boxes is not None:
            for box in boxes:
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                labels_seen.append(label)
                if label == _CROWD_CLASS:
                    persons += 1
                if label in _SCREEN_CLASSES:
                    has_screen = True
                if label in _OFFTOPIC:
                    offtopic_hits += 1
        person_counts.append(persons)
        if has_screen:
            screen_hits += 1

    mean_persons = sum(person_counts) / max(len(person_counts), 1)
    flags: List[str] = []
    reject_reasons: List[str] = []

    has_screen = screen_hits >= 2
    if has_screen:
        flags.append("has_screen")
    if mean_persons >= 5:
        reject_reasons.append("reject_crowded")
    if offtopic_hits >= 3 and not has_screen:
        reject_reasons.append("reject_offtopic_objects")
    if mean_persons >= 3:
        flags.append("avoid_as_hook")
    if has_screen and 1 <= mean_persons <= 2:
        flags.append("office_vibe")
    if has_screen and "avoid_as_hook" not in flags:
        flags.append("good_for_hook")

    return {
        "yolo_model": "yolov8n",
        "screen_hits": screen_hits,
        "mean_persons": round(mean_persons, 2),
        "offtopic_hits": offtopic_hits,
        "labels_sample": sorted(set(labels_seen))[:20],
        "flags": flags,
        "reject": bool(reject_reasons),
        "reject_reasons": reject_reasons,
    }


def analyze_clip(
    video: Path,
    work: Path,
    *,
    run_yolo: bool = True,
    min_duration: float = 5.0,
    max_duration: float = 30.0,
) -> Dict[str, Any]:
    """Full QA payload for sidecar JSON."""
    probe = probe_video(video)
    tech_reasons = ffprobe_gate(
        probe,
        min_duration=min_duration,
        max_duration=max_duration,
    )
    qa: Dict[str, Any] = {
        "probe": probe,
        "tech_reject_reasons": tech_reasons,
        "flags": [],
        "reject": bool(tech_reasons),
        "reject_reasons": list(tech_reasons),
        "yolo_status": "skipped",
    }

    if tech_reasons:
        return qa

    if not run_yolo:
        qa["yolo_status"] = "disabled"
        return qa

    if not yolo_available():
        qa["yolo_status"] = "missing_ultralytics"
        return qa

    try:
        yolo = run_yolo_on_video(video, work)
        qa["yolo_status"] = "ok"
        qa["yolo"] = yolo
        qa["flags"] = list(yolo.get("flags") or [])
        if yolo.get("reject"):
            qa["reject"] = True
            qa["reject_reasons"] = list(qa["reject_reasons"]) + list(
                yolo.get("reject_reasons") or []
            )
    except Exception as exc:  # noqa: BLE001 — keep fill going
        log.warning("YOLO failed for %s: %s", video.name, exc)
        qa["yolo_status"] = f"error:{type(exc).__name__}"

    return qa
