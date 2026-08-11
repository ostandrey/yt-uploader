"""
Post-render Shorts QA: rule scores always; optional vision LLM on keyframes.

Not YOLO (that's B-roll frames at fill time). This scores the finished Short
for retention / montage / interest so the owner can iterate.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio_ffmpeg
import requests
from dotenv import load_dotenv

from src.content.short_script_generator import is_complete_clause

log = logging.getLogger(__name__)

SOFT_FILLER = (
    "markets are watching",
    "traders are reacting",
    "analysis eyes",
    "this headline could shift",
    "developing story",
)


@dataclass
class QaFinding:
    code: str
    severity: str  # pass | warn | fail
    detail: str


@dataclass
class ShortsQaReport:
    score: int
    findings: List[QaFinding] = field(default_factory=list)
    vision_notes: str = ""
    source: str = "rules"

    def as_telegram(self) -> str:
        lines = [f"Shorts QA: {self.score}/100 ({self.source})"]
        for item in self.findings:
            mark = {"fail": "FAIL", "warn": "WARN", "pass": "OK"}.get(
                item.severity, item.severity.upper()
            )
            lines.append(f"  {mark} {item.code}: {item.detail}")
        if self.vision_notes:
            lines.append("")
            lines.append(self.vision_notes[:1200])
        return "\n".join(lines)


def _llm_config() -> Optional[tuple[str, str, str]]:
    load_dotenv()
    if os.getenv("COPY_LLM_ENABLED", "").strip().lower() in ("0", "false", "off", "no"):
        return None
    key = os.getenv("COPY_LLM_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("COPY_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    base = os.getenv("COPY_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return key, model, base


def _probe_duration(path: Path) -> float:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in (result.stderr or "").splitlines():
        if "Duration:" in line:
            raw = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = raw.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 0.0


def _extract_keyframes(video: Path, work_dir: Path, count: int = 4) -> List[Path]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    work_dir.mkdir(parents=True, exist_ok=True)
    # 0.4s hook, ~2s after hook, midpoint, near end
    stamps = ["0.4", "1.8", "12", "22"]
    paths: List[Path] = []
    for index, stamp in enumerate(stamps[:count]):
        out = work_dir / f"qa_frame_{index}.jpg"
        cmd = [
            ffmpeg, "-y", "-ss", stamp, "-i", str(video),
            "-frames:v", "1", "-q:v", "4", str(out),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            paths.append(out)
    return paths


def _score_rules(meta: Dict[str, Any], script: str) -> tuple[int, List[QaFinding]]:
    findings: List[QaFinding] = []
    score = 100
    duration = float(meta.get("duration_sec") or 0)
    sentences = int(meta.get("sentences") or 0)
    outro = float(meta.get("outro_sec") or 0)
    stats = meta.get("stat_overlays") or []
    sources = meta.get("broll_sources") or {}
    chart = int(sources.get("chart") or 0)
    local = int(sources.get("local") or 0)
    segments = int(meta.get("broll_segments") or 0)

    if 18 <= duration <= 32:
        findings.append(QaFinding("duration", "pass", f"{duration:.1f}s in 18-32s band"))
    elif 14 <= duration <= 40:
        score -= 10
        findings.append(QaFinding("duration", "warn", f"{duration:.1f}s outside sweet 18-32s"))
    else:
        score -= 25
        findings.append(QaFinding("duration", "fail", f"{duration:.1f}s too short/long for feed"))

    if 3 <= sentences <= 5:
        findings.append(QaFinding("beats", "pass", f"{sentences} spoken beats"))
    else:
        score -= 10
        findings.append(QaFinding("beats", "warn", f"{sentences} sentences (want 3-5)"))

    if outro <= 1.5:
        findings.append(QaFinding("outro", "pass", f"{outro:.1f}s brand card"))
    else:
        score -= 15
        findings.append(QaFinding("outro", "fail", f"{outro:.1f}s ending feels like a second story"))

    if stats:
        findings.append(QaFinding("hook_stat", "pass", ", ".join(str(s) for s in stats[:3])))
    else:
        score -= 12
        findings.append(QaFinding("hook_stat", "warn", "no money/% chip in first 2s"))

    if segments and chart >= max(segments - 1, 1):
        score -= 18
        findings.append(QaFinding("broll", "fail", "mostly chart cards — weak motion"))
    elif local:
        findings.append(QaFinding("broll", "pass", f"local clips={local} chart={chart}"))
    else:
        score -= 4
        findings.append(QaFinding("broll", "warn", f"no local library (pexels/chart={sources})"))

    lower = (script or "").lower()
    dangling = [
        line for line in (script or "").splitlines()
        if line.strip() and not is_complete_clause(line)
    ]
    if dangling:
        score -= 15
        findings.append(QaFinding("script", "fail", f"dangling line: {dangling[0][:80]}"))
    filler = [p for p in SOFT_FILLER if p in lower]
    if filler:
        score -= 10
        findings.append(QaFinding("interest", "warn", f"soft filler: {filler[0]}"))
    else:
        findings.append(QaFinding("interest", "pass", "no known filler templates"))

    return max(0, min(100, score)), findings


def _vision_notes(frames: List[Path], title: str, script: str) -> str:
    cfg = _llm_config()
    if not cfg or not frames:
        return ""
    key, model, base = cfg
    images = []
    for path in frames[:4]:
        raw = path.read_bytes()
        b64 = base64.standard_b64encode(raw).decode("ascii")
        images.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    prompt = (
        "You are Reel, a Shorts editor for Coin Wire (faceless crypto news). "
        "These frames are from one vertical Short (start, ~2s, mid, near end). "
        f"Title: {title}\nScript:\n{script}\n\n"
        "Score in 4 short bullets: (1) first-2s hook, (2) montage energy / cut variety, "
        "(3) subtitle vs ticker collision, (4) ending / would a stranger swipe. "
        "Be blunt. No em dashes. Max 80 words."
    )
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}, *images],
            }
        ],
        "max_tokens": 220,
        "temperature": 0.3,
    }
    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        return "Vision: " + text
    except Exception as exc:  # noqa: BLE001
        log.warning("Vision QA skipped: %s", exc)
        return f"Vision skipped: {exc}"


def review_short(
    video_path: Path,
    *,
    work_dir: Optional[Path] = None,
    script: str = "",
    title: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ShortsQaReport:
    video_path = Path(video_path)
    work_dir = Path(work_dir) if work_dir else video_path.parent.parent / "renders" / video_path.stem
    meta = dict(metadata or {})
    meta_path = work_dir / "metadata.json"
    if not meta and meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        except (OSError, json.JSONDecodeError):
            meta = {}
    title = title or str(meta.get("title") or video_path.stem)
    if not script:
        script = str(meta.get("script") or "")
    if not meta.get("duration_sec") and video_path.is_file():
        try:
            meta["duration_sec"] = _probe_duration(video_path)
        except Exception:  # noqa: BLE001
            meta["duration_sec"] = 0.0

    score, findings = _score_rules(meta, script)
    frames: List[Path] = []
    vision = ""
    if video_path.exists() and _llm_config():
        try:
            frames = _extract_keyframes(video_path, work_dir)
            vision = _vision_notes(frames, title, script)
        except Exception as exc:  # noqa: BLE001
            vision = f"Vision skipped: {exc}"
    source = "rules+vision" if vision.startswith("Vision:") else "rules"
    if vision.startswith("Vision:"):
        # Mild bump if vision ran; score stays rule-led
        pass
    report = ShortsQaReport(
        score=score, findings=findings, vision_notes=vision, source=source
    )
    qa_path = work_dir / "shorts_qa.json"
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        qa_path.write_text(
            json.dumps(
                {
                    "score": report.score,
                    "source": report.source,
                    "findings": [item.__dict__ for item in report.findings],
                    "vision_notes": report.vision_notes,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return report
