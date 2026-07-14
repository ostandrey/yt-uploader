"""
Batch-fill local B-roll library from Pexels / Pixabay, then mark with QA (ffprobe + YOLO).

Rejected clips stay on disk under category/_rejected/ (or flagged in sidecar)
so we do not re-download the same stock IDs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from src.media.broll_library import DEFAULT_LIBRARY, VALID_CATEGORIES
from src.media.broll_qa import analyze_clip, yolo_available
from src.media.broll_queries import CATEGORY_QUERIES, SUPPORTED_SOURCES
from src.media.stock_video_fetcher import StockVideoFetcher

log = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"


@dataclass
class FillConfig:
    library_root: Path = DEFAULT_LIBRARY
    max_clips_per_category: int = 40
    max_downloads_per_run: int = 20
    min_duration_sec: float = 5.0
    max_duration_sec: float = 30.0
    prefer_portrait: bool = True
    run_yolo: bool = True
    move_rejects: bool = True
    categories: List[str] = field(default_factory=lambda: sorted(VALID_CATEGORIES))
    sources: List[str] = field(default_factory=lambda: list(SUPPORTED_SOURCES))

    @classmethod
    def from_yaml(cls, config: dict, library_root: Optional[Path] = None) -> "FillConfig":
        block = (config.get("broll_library") or {}) if config else {}
        cats = block.get("categories") or sorted(VALID_CATEGORIES)
        sources = block.get("sources") or list(SUPPORTED_SOURCES)
        return cls(
            library_root=library_root or DEFAULT_LIBRARY,
            max_clips_per_category=int(block.get("max_clips_per_category", 40)),
            max_downloads_per_run=int(block.get("max_downloads_per_run", 20)),
            min_duration_sec=float(block.get("min_duration_sec", 5)),
            max_duration_sec=float(block.get("max_duration_sec", 30)),
            prefer_portrait=bool(block.get("prefer_portrait", True)),
            run_yolo=bool(block.get("run_yolo_on_fill", True)),
            move_rejects=bool(block.get("move_rejects", True)),
            categories=[c for c in cats if c in VALID_CATEGORIES],
            sources=[s for s in sources if s in SUPPORTED_SOURCES],
        )


def _meta_path(mp4: Path) -> Path:
    return mp4.with_suffix(".meta.json")


def load_known_ids(library_root: Path) -> set[str]:
    known: set[str] = set()
    for meta in library_root.rglob("*.meta.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            sid = data.get("source_id")
            src = data.get("source")
            if sid and src:
                known.add(f"{src}:{sid}")
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return known


def count_usable_clips(category_dir: Path) -> int:
    if not category_dir.is_dir():
        return 0
    n = 0
    for mp4 in category_dir.glob("*.mp4"):
        meta = _meta_path(mp4)
        if meta.exists():
            try:
                if json.loads(meta.read_text(encoding="utf-8")).get("reject"):
                    continue
            except (OSError, json.JSONDecodeError):
                pass
        if mp4.stat().st_size > 50_000:
            n += 1
    return n


def _search_pexels(
    fetcher: StockVideoFetcher,
    query: str,
    *,
    prefer_portrait: bool,
    min_dur: float,
    max_dur: float,
) -> List[Dict[str, Any]]:
    if not fetcher.pexels_api_key or fetcher.pexels_api_key == "your_pexels_api_key_here":
        return []
    orientation = "portrait" if prefer_portrait else "landscape"
    try:
        response = requests.get(
            PEXELS_VIDEO_URL,
            headers={"Authorization": fetcher.pexels_api_key},
            params={
                "query": query,
                "per_page": 15,
                "orientation": orientation,
                "size": "large",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Pexels search failed (%s): %s", query, exc)
        return []

    out: List[Dict[str, Any]] = []
    for item in response.json().get("videos", []):
        duration = float(item.get("duration") or 0)
        if duration < min_dur or duration > max_dur:
            continue
        parsed = fetcher._video_from_pexels_item(item, query)
        if not parsed:
            continue
        vid = str(item.get("id") or "")
        if not vid:
            continue
        parsed["source_id"] = vid
        parsed["query"] = query
        out.append(parsed)
    return out


def _search_pixabay(
    fetcher: StockVideoFetcher,
    query: str,
    *,
    min_dur: float,
    max_dur: float,
) -> List[Dict[str, Any]]:
    if not fetcher.pixabay_api_key or fetcher.pixabay_api_key == "your_pixabay_api_key_here":
        return []
    try:
        response = requests.get(
            PIXABAY_VIDEO_URL,
            params={
                "key": fetcher.pixabay_api_key,
                "q": query,
                "per_page": 12,
                "video_type": "film",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Pixabay search failed (%s): %s", query, exc)
        return []

    out: List[Dict[str, Any]] = []
    for hit in response.json().get("hits", []):
        duration = float(hit.get("duration") or 0)
        if duration and (duration < min_dur or duration > max_dur):
            continue
        videos = hit.get("videos") or {}
        chosen = videos.get("large") or videos.get("medium") or videos.get("small")
        if not chosen or not chosen.get("url"):
            continue
        vid = str(hit.get("id") or "")
        if not vid:
            continue
        out.append({
            "url": chosen["url"],
            "source": "pixabay",
            "source_id": vid,
            "keyword": query,
            "query": query,
            "type": "video",
            "duration": duration,
            "width": chosen.get("width", 0),
            "height": chosen.get("height", 0),
        })
    return out


def _write_meta(mp4: Path, payload: Dict[str, Any]) -> None:
    _meta_path(mp4).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _file_hash(path: Path, limit: int = 1024 * 256) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        h.update(handle.read(limit))
    return h.hexdigest()[:16]


def process_downloaded(
    mp4: Path,
    *,
    category: str,
    video: Dict[str, Any],
    cfg: FillConfig,
    work_root: Path,
) -> Dict[str, Any]:
    work = work_root / mp4.stem
    qa = analyze_clip(
        mp4,
        work,
        run_yolo=cfg.run_yolo,
        min_duration=cfg.min_duration_sec,
        max_duration=cfg.max_duration_sec,
    )
    meta = {
        "source": video.get("source"),
        "source_id": video.get("source_id"),
        "query": video.get("query") or video.get("keyword"),
        "category": category,
        "url": video.get("url"),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "sha256_prefix": _file_hash(mp4),
        "duration": video.get("duration"),
        "width": video.get("width"),
        "height": video.get("height"),
        "reject": bool(qa.get("reject")),
        "reject_reasons": qa.get("reject_reasons") or [],
        "flags": qa.get("flags") or [],
        "qa": qa,
    }
    final_path = mp4
    if meta["reject"] and cfg.move_rejects:
        rejected_dir = mp4.parent / "_rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        dest = rejected_dir / mp4.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(mp4), str(dest))
        final_path = dest
        meta_src = _meta_path(mp4)
        if meta_src.exists():
            meta_src.unlink(missing_ok=True)
    _write_meta(final_path, meta)
    # clean frame workdir
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    return {"path": str(final_path), **{k: meta[k] for k in ("reject", "flags", "reject_reasons")}}


def fill_broll_library(
    cfg: FillConfig,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    load_dotenv()
    fetcher = StockVideoFetcher(library_path=cfg.library_root)
    known = load_known_ids(cfg.library_root)
    work_root = cfg.library_root / "_qa_work"
    downloaded = 0
    rejected = 0
    kept = 0
    skipped_dup = 0
    per_category: Dict[str, Any] = {}

    log.info(
        "Fill start: max_run=%s yolo=%s available=%s sources=%s",
        cfg.max_downloads_per_run,
        cfg.run_yolo,
        yolo_available() if cfg.run_yolo else False,
        cfg.sources,
    )

    for category in cfg.categories:
        if downloaded >= cfg.max_downloads_per_run:
            break
        cat_dir = cfg.library_root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        usable = count_usable_clips(cat_dir)
        need = max(cfg.max_clips_per_category - usable, 0)
        per_category[category] = {"had": usable, "need": need, "added": 0, "rejected": 0}
        if need <= 0:
            continue

        queries = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["default"])
        candidates: List[Dict[str, Any]] = []
        for query in queries:
            if "pexels" in cfg.sources:
                candidates.extend(
                    _search_pexels(
                        fetcher,
                        query,
                        prefer_portrait=cfg.prefer_portrait,
                        min_dur=cfg.min_duration_sec,
                        max_dur=cfg.max_duration_sec,
                    )
                )
            if "pixabay" in cfg.sources:
                candidates.extend(
                    _search_pixabay(
                        fetcher,
                        query,
                        min_dur=cfg.min_duration_sec,
                        max_dur=cfg.max_duration_sec,
                    )
                )

        # Prefer portrait-ish
        candidates.sort(
            key=lambda v: (
                0 if int(v.get("height") or 0) >= int(v.get("width") or 0) else 1,
                -(int(v.get("width") or 0) * int(v.get("height") or 0)),
            )
        )

        for video in candidates:
            if downloaded >= cfg.max_downloads_per_run:
                break
            if per_category[category]["added"] + usable >= cfg.max_clips_per_category:
                break
            key = f"{video.get('source')}:{video.get('source_id')}"
            if key in known:
                skipped_dup += 1
                continue

            stem = f"{video['source']}_{video['source_id']}"
            target = cat_dir / f"{stem}.mp4"
            if target.exists() or (cat_dir / "_rejected" / f"{stem}.mp4").exists():
                known.add(key)
                skipped_dup += 1
                continue

            if dry_run:
                log.info("[dry-run] would download %s → %s", key, target)
                known.add(key)
                downloaded += 1
                per_category[category]["added"] += 1
                continue

            path = fetcher.download_video(video, target, use_cache=False)
            if not path:
                log.warning("Download failed: %s", key)
                continue

            known.add(key)
            downloaded += 1
            result = process_downloaded(
                path,
                category=category,
                video=video,
                cfg=cfg,
                work_root=work_root,
            )
            if result.get("reject"):
                rejected += 1
                per_category[category]["rejected"] += 1
                log.info("Rejected %s (%s)", key, result.get("reject_reasons"))
            else:
                kept += 1
                per_category[category]["added"] += 1
                usable += 1
                log.info(
                    "Kept %s flags=%s",
                    key,
                    result.get("flags"),
                )

    if work_root.exists():
        shutil.rmtree(work_root, ignore_errors=True)

    return {
        "downloaded": downloaded,
        "kept": kept,
        "rejected": rejected,
        "skipped_dup": skipped_dup,
        "dry_run": dry_run,
        "yolo_available": yolo_available(),
        "per_category": per_category,
    }
