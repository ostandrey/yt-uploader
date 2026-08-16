from pathlib import Path

from src.media import bg_music


def test_ensure_background_music_uses_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("COIN_WIRE_DATA", str(tmp_path))
    dummy = tmp_path / "assets" / "background.mp3"
    dummy.parent.mkdir(parents=True)
    dummy.write_bytes(b"0" * 20_000)
    found = bg_music.ensure_background_music()
    assert found == dummy


def test_mix_skips_when_music_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COIN_WIRE_DATA", str(tmp_path))
    monkeypatch.setattr(bg_music, "DOWNLOAD_URLS", ())
    monkeypatch.setattr(bg_music, "_env_urls", lambda: ())
    monkeypatch.setattr(bg_music, "_pull_from_r2", lambda _dest: False)
    monkeypatch.setattr(bg_music, "synth_music_bed", lambda dest=None: None)
    monkeypatch.setattr(bg_music, "_candidate_paths", lambda: [tmp_path / "assets" / "background.mp3"])
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"1" * 100)
    out = tmp_path / "mixed.mp3"
    assert bg_music.mix_background_music(voice, out) == voice


def test_resolve_falls_back_to_synth(tmp_path, monkeypatch):
    monkeypatch.setenv("COIN_WIRE_DATA", str(tmp_path))
    monkeypatch.delenv("SHORTS_MUSIC_URL", raising=False)
    monkeypatch.setattr(bg_music, "DOWNLOAD_URLS", ())
    monkeypatch.setattr(bg_music, "_pull_from_r2", lambda _dest: False)
    monkeypatch.setattr(bg_music, "_candidate_paths", lambda: [tmp_path / "assets" / "background.mp3"])
    pad = tmp_path / "assets" / "background_pad.mp3"
    pad.parent.mkdir(parents=True)
    pad.write_bytes(b"2" * 20_000)
    monkeypatch.setattr(bg_music, "synth_music_bed", lambda dest=None: pad)
    path, source = bg_music.resolve_background_music()
    assert path == pad
    assert source == "synth"


def test_synth_music_bed_writes_usable_file(tmp_path, monkeypatch):
    monkeypatch.setenv("COIN_WIRE_DATA", str(tmp_path))
    out = bg_music.synth_music_bed(tmp_path / "pad.mp3")
    assert out is not None
    assert out.stat().st_size > 10_000
