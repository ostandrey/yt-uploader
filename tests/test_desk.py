from pathlib import Path

from src.desk import auth, catalog, db


def test_session_roundtrip(monkeypatch):
    monkeypatch.setenv("DESK_PASSWORD", "test-pass-desk")
    monkeypatch.setenv("DESK_SECRET", "test-secret-desk")
    monkeypatch.setenv("DESK_SESSION_HOURS", "1")
    token = auth.issue_session()
    assert auth.verify_session(token)
    assert not auth.verify_session(token + "x")
    assert not auth.verify_session("1.abcd.ffff")


def test_password_compare(monkeypatch):
    monkeypatch.setenv("DESK_PASSWORD", "abc")
    assert auth.check_password("abc")
    assert not auth.check_password("abd")
    assert not auth.check_password("")
    assert not auth.check_password("ab")


def test_write_and_load_latest(tmp_path, monkeypatch):
    videos = tmp_path / "videos"
    videos.mkdir()
    video = videos / "short.mp4"
    video.write_bytes(b"fake-mp4")
    work = tmp_path / "render"
    work.mkdir()
    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    monkeypatch.setattr(catalog, "VIDEOS_DIR", videos)
    monkeypatch.setattr(catalog, "LATEST_FILE", tmp_path / "desk_latest.json")
    catalog.write_desk_pack(
        title="Bitcoin ETF inflows",
        video_path=video,
        work_dir=work,
        ig_caption="hello ig",
        threads_text="hello threads",
        youtube_url="https://youtu.be/x",
        qa_score=71,
    )
    latest = catalog.load_latest()
    assert latest is not None
    assert latest["ig_caption"] == "hello ig"
    assert latest["threads_text"] == "hello threads"
    assert Path(latest["video_path"]).name == "short.mp4"
    assert latest["id"]
    marked = db.set_mark(latest["id"], "tiktok", True)
    assert marked["marks"]["tiktok"] is True
    snap = catalog.stats_snapshot()
    assert snap["shorts_on_desk"] == 1
    assert snap["posted_tiktok"] == 1
    assert snap["latest_qa"] == 71
    assert catalog.resolve_video_file(latest) == video.resolve()


def test_login_and_today(tmp_path, monkeypatch):
    videos = tmp_path / "videos"
    videos.mkdir()
    video = videos / "short.mp4"
    video.write_bytes(b"fake-mp4")
    monkeypatch.setenv("DESK_PASSWORD", "desk-pass")
    monkeypatch.setenv("DESK_SECRET", "desk-secret")
    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    monkeypatch.setattr(catalog, "VIDEOS_DIR", videos)
    monkeypatch.setattr(catalog, "LATEST_FILE", tmp_path / "desk_latest.json")
    work = tmp_path / "render"
    slides = work / "ig_carousel"
    slides.mkdir(parents=True)
    (slides / "01.jpg").write_bytes(b"jpeg-one")
    (slides / "caption.txt").write_text("carousel body", encoding="utf-8")
    catalog.write_desk_pack(
        title="Desk title",
        video_path=video,
        work_dir=work,
        ig_caption="ig line",
        threads_text="th line",
    )
    from fastapi.testclient import TestClient

    from src.desk.app import app

    client = TestClient(app, follow_redirects=False)
    guest = client.get("/")
    assert guest.status_code == 303
    assert "/login" in guest.headers["location"]
    bad = client.post("/login", data={"password": "nope"})
    assert bad.status_code == 401
    ok = client.post("/login", data={"password": "desk-pass"})
    assert ok.status_code == 303
    assert "cw_desk=" in (ok.headers.get("set-cookie") or "")
    home = client.get("/")
    assert home.status_code == 200
    assert "Desk title" in home.text
    assert 'data-copy="ig_caption"' in home.text
    assert 'data-share="tiktok"' in home.text
    assert 'id="pack-json"' in home.text
    assert 'id="dock"' in home.text
    assert "Instagram карусель" in home.text
    assert "data-share-carousel" in home.text
    slide = client.get("/media/ig/01.jpg")
    assert slide.status_code == 200
    assert slide.content == b"jpeg-one"
    zipped = client.get("/media/ig.zip")
    assert zipped.status_code == 200
    media = client.get("/media/latest.mp4")
    assert media.status_code == 200
    assert media.content == b"fake-mp4"
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    anon = TestClient(app, follow_redirects=False)
    assert anon.get("/media/latest.mp4").status_code == 401


def test_health_without_password(monkeypatch):
    monkeypatch.delenv("DESK_PASSWORD", raising=False)
    from fastapi.testclient import TestClient

    from src.desk.app import app

    client = TestClient(app, follow_redirects=False)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "desk": False}
    assert client.get("/").status_code == 404
