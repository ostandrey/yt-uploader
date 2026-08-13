from pathlib import Path

from src.desk import auth, catalog, db


def test_editorial_new_vs_old_badges(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    monkeypatch.setenv("DESK_TZ", "UTC")
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    now = datetime.now(timezone.utc)
    catalog.write_editorial_items(
        [
            {
                "id": "new-1",
                "kind": "opinion",
                "label": "Threads — opinion",
                "text": "Fresh Anchorpoint take",
                "created_at": now.isoformat(),
                "done": False,
            },
            {
                "id": "old-1",
                "kind": "opinion",
                "label": "Threads — opinion",
                "text": "Old Fidelity take",
                "created_at": (now - timedelta(hours=9)).isoformat(),
                "done": False,
            },
            {
                "id": "done-1",
                "kind": "context",
                "label": "Telegram — контекст",
                "text": "Already posted context",
                "created_at": now.isoformat(),
                "done": True,
            },
        ]
    )
    items = catalog.load_editorial_items(scope="today")
    by_id = {item["id"]: item for item in items}
    assert by_id["new-1"]["badge"] == "НОВЕ"
    assert by_id["new-1"]["badge_kind"] == "new"
    assert by_id["new-1"]["tab"] == "threads"
    if by_id.get("old-1"):
        assert by_id["old-1"]["badge"] == "РАНІШЕ"
    assert by_id["done-1"]["badge"] == "ГОТОВО"
    assert by_id["done-1"]["tab"] == "telegram"
    assert items[0]["id"] == "new-1"
    marked = catalog.set_editorial_done("new-1", True)
    assert marked["done"] is True
    assert marked["badge"] == "ГОТОВО"
    tabs = catalog.desk_tabs(None, catalog.load_editorial_items(scope="today"))
    by_tab = {t["id"]: t["badge"] for t in tabs}
    assert "all" not in by_tab
    assert by_tab["telegram"] == 0  # done, not new
    assert "threads" in by_tab


def test_editorial_history_keeps_all_posts(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("DESK_DB", str(tmp_path / "desk.sqlite"))
    monkeypatch.setenv("DESK_TZ", "UTC")
    db.reset_init_for_tests()
    monkeypatch.setattr(catalog, "STORAGE", tmp_path)
    now = datetime.now(timezone.utc)
    items = [
        {
            "id": f"e{i}",
            "kind": "opinion",
            "label": "Threads — opinion",
            "text": f"Post number {i} about markets",
            "created_at": (now - timedelta(days=i)).isoformat(),
            "done": False,
        }
        for i in range(12)
    ]
    catalog.write_editorial_items(items)
    assert len(catalog.load_editorial_items(scope="all")) == 12
    today = catalog.load_editorial_items(scope="today")
    assert {row["id"] for row in today} == {"e0"}
    history = catalog.load_editorial_items(scope="history")
    assert len(history) == 11
    assert catalog.editorial_history_count() == 11
    parts = catalog.split_question_post(
        "If Goldman pays $2.25B for Neos, who controls the next ETFs?\n\nWall Street banks\nIndependent issuers"
    )
    assert parts["question"].startswith("If Goldman")
    assert parts["a"] == "Wall Street banks"
    assert parts["b"] == "Independent issuers"
    page = catalog.history_page()
    assert page["count"] == 11
    assert page["groups"][0]["editorial"]


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


def test_public_pack_never_uses_filename_slug(tmp_path, monkeypatch):
    from src.content.copy_guard import safe_caption
    from src.desk.app import _public_pack

    pack = {
        "title": "short_20260811_2200_bitcoin_stuck_as_etf_inflows_o",
        "ig_caption": "",
        "threads_text": "short 20260811 2200 bitcoin stuck as etf inflows o",
        "marks": {"tiktok": False, "instagram": False, "threads": False},
    }
    monkeypatch.setattr("src.desk.catalog.list_carousel_slides", lambda: [])
    monkeypatch.setattr("src.desk.catalog.carousel_caption_text", lambda: pack["title"])
    public = _public_pack(pack)
    assert public["title"] == "Short готовий"
    assert public["ig_caption"] == ""
    assert public["caption_ready"] is False
    assert "threads_text" not in public
    assert safe_caption(pack["title"]) == ""


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
    assert 'href="/history"' in home.text
    hist = client.get("/history")
    assert hist.status_code == 200
    assert "Історія" in hist.text
    assert 'data-copy="ig_caption"' in home.text
    assert 'data-share="tiktok"' in home.text
    assert 'data-share="threads"' not in home.text
    assert 'id="pack-json"' in home.text
    assert 'id="dock"' in home.text
    assert "Instagram Reel" in home.text
    assert "Карусель" in home.text or "карусель" in home.text.lower() or "carousel" in home.text.lower()
    assert "data-share-carousel" in home.text
    assert "data-save-carousel" in home.text
    assert "Наступна перевірка" in home.text
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
    body = res.json()
    assert body["ok"] is True
    assert body["desk"] is False
    assert "storage" in body
    assert "path" in body["storage"]
    assert client.get("/").status_code == 404
