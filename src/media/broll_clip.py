"""
CLIP topic scoring for B-roll clips (category fit).

Uses open_clip when installed. Never scores text posts — images/frames only.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import imageio_ffmpeg

from src.media.broll_library import VALID_CATEGORIES

log = logging.getLogger(__name__)

# Primary CLIP prompts per category (more specific than fill queries)
CATEGORY_PROMPTS: Dict[str, str] = {
    "bitcoin": "bitcoin cryptocurrency trading chart on a computer monitor",
    "ethereum": "ethereum blockchain network and crypto technology",
    "macro": "wall street stock market ticker federal reserve finance news",
    "regulation": "courthouse government building legal documents compliance",
    "security": "cybersecurity hacking code digital lock server room",
    "defi": "decentralized finance smart contracts fintech mobile app",
    "default": "business finance technology city markets abstract",
}


def clip_available() -> bool:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


_MODEL = None
_PREPROCESS = None
_TOKENIZER = None
_DEVICE = None
_TEXT_FEATS: Optional[Dict[str, Any]] = None


def _load_model():
    global _MODEL, _PREPROCESS, _TOKENIZER, _DEVICE, _TEXT_FEATS
    if _MODEL is not None:
        return
    import open_clip
    import torch

    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    _MODEL, _, _PREPROCESS = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    _TOKENIZER = open_clip.get_tokenizer("ViT-B-32")
    _MODEL = _MODEL.to(_DEVICE).eval()

    prompts = [CATEGORY_PROMPTS[c] for c in sorted(VALID_CATEGORIES)]
    cats = sorted(VALID_CATEGORIES)
    with torch.no_grad():
        tokens = _TOKENIZER(prompts).to(_DEVICE)
        feats = _MODEL.encode_text(tokens)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    _TEXT_FEATS = {cat: feats[i] for i, cat in enumerate(cats)}


def _extract_frames(video: Path, work: Path, n: int = 3) -> List[Path]:
    work.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    seeks = [1.0 + i * 2.0 for i in range(n)]
    paths: List[Path] = []
    for i, t in enumerate(seeks):
        out = work / f"clip_frame_{i}.jpg"
        cmd = [
            ffmpeg, "-y", "-ss", f"{t:.1f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(out),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, check=False)
            if out.exists() and out.stat().st_size > 500:
                paths.append(out)
        except (OSError, subprocess.SubprocessError):
            continue
    return paths


def score_video_categories(video: Path, work: Path) -> Dict[str, float]:
    """Return cosine similarity per category (0..1-ish)."""
    import torch
    from PIL import Image

    _load_model()
    assert _MODEL is not None and _PREPROCESS is not None and _TEXT_FEATS is not None

    frames = _extract_frames(video, work / "clip_frames", n=3)
    if not frames:
        return {}

    images = []
    for frame in frames:
        try:
            images.append(_PREPROCESS(Image.open(frame).convert("RGB")))
        except OSError:
            continue
    if not images:
        return {}

    batch = torch.stack(images).to(_DEVICE)
    with torch.no_grad():
        img_feat = _MODEL.encode_image(batch)
        img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
        mean_feat = img_feat.mean(dim=0)
        mean_feat = mean_feat / mean_feat.norm()

    scores: Dict[str, float] = {}
    for cat, text_feat in _TEXT_FEATS.items():
        sim = float((mean_feat @ text_feat).item())
        scores[cat] = round(sim, 4)
    return scores


def best_category(
    scores: Dict[str, float],
    *,
    current: str,
    margin: float = 0.05,
) -> Tuple[str, float, Optional[str]]:
    """
    Return (best_cat, best_score, suggest_move_to or None).
    Suggest move only if another category beats current by margin.
    """
    if not scores:
        return current, 0.0, None
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    current_score = scores.get(current, 0.0)
    suggest = None
    if best_cat != current and (best_score - current_score) >= margin:
        suggest = best_cat
    return best_cat, best_score, suggest


def index_one_clip(
    mp4: Path,
    *,
    category: str,
    work_root: Path,
    apply_move: bool = False,
    library_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Score one clip, update meta.json, optionally move to better category."""
    import json
    import shutil

    from src.media.broll_library import DEFAULT_LIBRARY

    library_root = library_root or DEFAULT_LIBRARY
    work = work_root / mp4.stem
    scores = score_video_categories(mp4, work)
    best_cat, best_score, suggest = best_category(scores, current=category)

    meta_path = mp4.with_suffix(".meta.json")
    meta: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}

    meta["clip_scores"] = scores
    meta["clip_best_category"] = best_cat
    meta["clip_best_score"] = best_score
    meta["clip_folder_score"] = scores.get(category, 0.0)
    meta["clip_suggest_move"] = suggest

    final = mp4
    if apply_move and suggest:
        dest_dir = library_root / suggest
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / mp4.name
        if not dest.exists():
            shutil.move(str(mp4), str(dest))
            # move meta
            if meta_path.exists():
                meta_path.unlink(missing_ok=True)
            final = dest
            meta["category"] = suggest
            meta["clip_moved_from"] = category
            meta_path = final.with_suffix(".meta.json")

    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)

    return {
        "path": str(final),
        "category": meta.get("category", category),
        "folder_score": meta.get("clip_folder_score"),
        "best": best_cat,
        "best_score": best_score,
        "suggest_move": suggest,
        "moved": bool(apply_move and suggest and final != mp4),
    }
