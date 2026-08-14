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
    monkeypatch.setattr(bg_music, "_candidate_paths", lambda: [tmp_path / "assets" / "background.mp3"])
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"1" * 100)
    out = tmp_path / "mixed.mp3"
    assert bg_music.mix_background_music(voice, out) == voice
