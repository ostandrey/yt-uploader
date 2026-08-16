from pathlib import Path

from src.storage_cleanup import (
    keep_newest_videos,
    over_budget,
    prune_broll_library,
    reclaim_volume,
    strip_render_dir,
)


def _work_dir(root: Path, name: str) -> Path:
    work = root / "renders" / name
    raw = work / "raw"
    raw.mkdir(parents=True)
    (raw / "seg_00.mp4").write_bytes(b"raw" * 200)
    (work / "concat.mp4").write_bytes(b"concat" * 200)
    (work / "metadata.json").write_text("{}", encoding="utf-8")
    (work / "thumbnail.jpg").write_bytes(b"jpg")
    carousel = work / "ig_carousel"
    carousel.mkdir()
    (carousel / "01.jpg").write_bytes(b"slide")
    return work


def test_strip_keeps_desk_assets(tmp_path: Path):
    work = _work_dir(tmp_path, "short_a")
    freed = strip_render_dir(work)
    assert freed > 0
    assert not (work / "raw").exists()
    assert not (work / "concat.mp4").exists()
    assert (work / "metadata.json").is_file()
    assert (work / "thumbnail.jpg").is_file()
    assert (work / "ig_carousel" / "01.jpg").is_file()


def test_keep_newest_videos_drops_older(tmp_path: Path):
    videos = tmp_path / "videos"
    videos.mkdir()
    names = ["old", "mid", "new"]
    for index, name in enumerate(names):
        path = videos / f"{name}.mp4"
        path.write_bytes(b"v" * 50)
        path.touch()
        stamp = 1_700_000_000 + index * 100
        import os

        os.utime(path, (stamp, stamp))
        _work_dir(tmp_path, name)
    out = keep_newest_videos(keep=1, root=tmp_path)
    assert out["removed_videos"] == 2
    assert (videos / "new.mp4").is_file()
    assert not (videos / "old.mp4").exists()
    assert not (tmp_path / "renders" / "old").exists()
    assert (tmp_path / "renders" / "new" / "thumbnail.jpg").is_file()


def test_prune_broll_library(tmp_path: Path):
    lib = tmp_path / "assets" / "broll_library" / "bitcoin"
    lib.mkdir(parents=True)
    (lib / "clip.mp4").write_bytes(b"clip" * 100)
    out = prune_broll_library(root=tmp_path)
    assert out["pruned"] is True
    assert not (tmp_path / "assets" / "broll_library").exists()


def test_reclaim_strips_and_prunes_without_touching_sqlite(tmp_path: Path):
    sqlite = tmp_path / "storage" / "coin_wire" / "desk.sqlite"
    sqlite.parent.mkdir(parents=True)
    sqlite.write_text("keep", encoding="utf-8")
    data = tmp_path
    storage = tmp_path / "storage" / "coin_wire"
    _work_dir(storage, "short_now")
    lib = data / "assets" / "broll_library"
    lib.mkdir(parents=True)
    (lib / "x.mp4").write_bytes(b"broll" * 80)
    out = reclaim_volume(retention_days=7, keep_latest_videos=3, root=storage, data=data)
    assert sqlite.read_text(encoding="utf-8") == "keep"
    assert out["pruned"]["pruned"] is True
    assert out["stripped"]["stripped_dirs"] == 1
    assert (storage / "renders" / "short_now" / "thumbnail.jpg").is_file()
    assert not (storage / "renders" / "short_now" / "concat.mp4").exists()


def test_over_budget_uses_injected_usage():
    assert over_budget(
        Path("."),
        usage={"total_bytes": 5_000_000_000, "used_bytes": 4_700_000_000, "free_bytes": 300_000_000, "used_ratio": 0.94},
    )
    assert not over_budget(
        Path("."),
        usage={"total_bytes": 5_000_000_000, "used_bytes": 2_000_000_000, "free_bytes": 3_000_000_000, "used_ratio": 0.4},
    )


def test_hobby_volume_skips_broll_library(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace

    from src.media.broll_sync import volume_too_small_for_library

    monkeypatch.setattr(
        "src.media.broll_sync.shutil.disk_usage",
        lambda _path: SimpleNamespace(total=5 * 1024**3, used=4 * 1024**3, free=1 * 1024**3),
    )
    assert volume_too_small_for_library(tmp_path)
    monkeypatch.setattr(
        "src.media.broll_sync.shutil.disk_usage",
        lambda _path: SimpleNamespace(total=50 * 1024**3, used=10 * 1024**3, free=40 * 1024**3),
    )
    assert not volume_too_small_for_library(tmp_path)
