"""B-roll scored pick + rotation."""

from __future__ import annotations

import json
from pathlib import Path

from src.media.broll_library import (
    clip_id,
    load_recently_used_ids,
    mark_clip_used,
    pick_local_clip,
    score_clip,
)


def _make_clip(folder: Path, name: str, flags: list[str]) -> Path:
    mp4 = folder / f"{name}.mp4"
    mp4.write_bytes(b"0" * 60_000)
    mp4.with_suffix(".meta.json").write_text(
        json.dumps({
            "source": "pexels",
            "source_id": name,
            "reject": False,
            "flags": flags,
            "qa": {"probe": {"width": 1080, "height": 1920, "portrait": True}},
        }),
        encoding="utf-8",
    )
    return mp4


def test_score_prefers_hook_flags(tmp_path: Path):
    cat = tmp_path / "bitcoin"
    cat.mkdir()
    weak = _make_clip(cat, "weak", [])
    strong = _make_clip(cat, "strong", ["has_screen", "good_for_hook"])
    assert score_clip(strong)[0] > score_clip(weak)[0]


def test_pick_prefers_high_score(tmp_path: Path, monkeypatch):
    cat = tmp_path / "bitcoin"
    cat.mkdir()
    _make_clip(cat, "weak", [])
    strong = _make_clip(cat, "strong", ["has_screen", "good_for_hook", "office_vibe"])
    used_file = tmp_path / "used.json"
    monkeypatch.setattr("src.media.broll_library.USED_CLIPS_FILE", used_file)
    # Enough draws that strong should dominate
    picks = [
        pick_local_clip("bitcoin", set(), tmp_path, persist_rotation=False)
        for _ in range(20)
    ]
    names = [p.name for p in picks if p]
    assert names.count(strong.name) >= 12


def test_mark_and_load_rotation(tmp_path: Path, monkeypatch):
    cat = tmp_path / "macro"
    cat.mkdir()
    clip = _make_clip(cat, "a1", ["has_screen"])
    used_file = tmp_path / "used.json"
    monkeypatch.setattr("src.media.broll_library.USED_CLIPS_FILE", used_file)
    mark_clip_used(clip, used_file)
    assert clip_id(clip) in load_recently_used_ids(used_file)
