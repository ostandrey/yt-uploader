"""CLIP score wiring into pick score."""

from __future__ import annotations

import json
from pathlib import Path

from src.media.broll_library import score_clip
from src.content.news_filter import build_market_takeaway


def test_clip_folder_score_boosts_pick(tmp_path: Path):
    cat = tmp_path / "regulation"
    cat.mkdir()
    weak = cat / "weak.mp4"
    strong = cat / "strong.mp4"
    for path, folder_score in ((weak, 0.15), (strong, 0.32)):
        path.write_bytes(b"0" * 60_000)
        path.with_suffix(".meta.json").write_text(
            json.dumps({
                "category": "regulation",
                "flags": [],
                "clip_folder_score": folder_score,
                "qa": {"probe": {"width": 1080, "height": 1920, "portrait": True}},
            }),
            encoding="utf-8",
        )
    assert score_clip(strong)[0] > score_clip(weak)[0]


def test_takeaway_no_developing_boilerplate():
    article = {
        "title": "Random protocol update ships quietly",
        "summary": "A small tooling release with no majors named.",
    }
    out = build_market_takeaway(article)
    assert "developing story" not in out.lower()
    assert "tend to drag" not in out.lower()
