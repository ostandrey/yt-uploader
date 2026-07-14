"""B-roll library reject filtering and fill config."""

from __future__ import annotations

import json
from pathlib import Path

from src.media.broll_fill import FillConfig, count_usable_clips, load_known_ids
from src.media.broll_library import list_library_clips, pick_local_clip
from src.media.broll_qa import ffprobe_gate


def test_ffprobe_gate_too_short():
    reasons = ffprobe_gate(
        {"duration_sec": 2.0, "width": 1080, "height": 1920, "portrait": True},
        min_duration=5.0,
    )
    assert any("too_short" in r for r in reasons)


def test_list_skips_rejected(tmp_path: Path):
    cat = tmp_path / "bitcoin"
    cat.mkdir()
    good = cat / "ok.mp4"
    bad = cat / "bad.mp4"
    good.write_bytes(b"0" * 60_000)
    bad.write_bytes(b"0" * 60_000)
    bad.with_suffix(".meta.json").write_text(
        json.dumps({"reject": True, "reject_reasons": ["reject_crowded"]}),
        encoding="utf-8",
    )
    clips = list_library_clips(tmp_path, "bitcoin")
    assert good.resolve() in {c.resolve() for c in clips}
    assert bad.resolve() not in {c.resolve() for c in clips}


def test_pick_ignores_rejected_folder(tmp_path: Path):
    cat = tmp_path / "macro"
    rejected = cat / "_rejected"
    rejected.mkdir(parents=True)
    (rejected / "junk.mp4").write_bytes(b"0" * 60_000)
    (cat / "keep.mp4").write_bytes(b"0" * 60_000)
    picked = pick_local_clip("macro", set(), tmp_path)
    assert picked is not None
    assert picked.name == "keep.mp4"


def test_count_usable_and_known_ids(tmp_path: Path):
    cat = tmp_path / "defi"
    cat.mkdir()
    mp4 = cat / "pexels_1.mp4"
    mp4.write_bytes(b"0" * 60_000)
    mp4.with_suffix(".meta.json").write_text(
        json.dumps({"source": "pexels", "source_id": "1", "reject": False}),
        encoding="utf-8",
    )
    assert count_usable_clips(cat) == 1
    assert "pexels:1" in load_known_ids(tmp_path)


def test_fill_config_from_yaml():
    cfg = FillConfig.from_yaml({
        "broll_library": {
            "max_downloads_per_run": 7,
            "run_yolo_on_fill": False,
            "sources": ["pexels"],
        }
    })
    assert cfg.max_downloads_per_run == 7
    assert cfg.run_yolo is False
    assert cfg.sources == ["pexels"]
