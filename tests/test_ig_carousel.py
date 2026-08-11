from pathlib import Path

from PIL import Image

from src.media.ig_carousel import build_what_moved, carousel_caption, render_what_moved


def test_what_moved_uses_number_from_article_only():
    slides = build_what_moved(
        {
            "title": "Bitcoin ETF inflows hit $4.6B in three days",
            "description": "Issuers reported $4.6B net inflows. SEC filing followed.",
            "script": "Bitcoin ETF inflows hit a new mark.\nFollow Coin Wire for the next move.",
            "source_link": "https://www.bloomberg.com/news/example",
        }
    )
    assert len(slides) == 6
    assert "$4.6B" in slides[1]["title"]
    assert slides[0]["kind"] == "hook"
    assert slides[-1]["kind"] == "cta"
    assert "bloomberg.com" in slides[4]["title"]


def test_what_moved_does_not_invent_money():
    slides = build_what_moved({"title": "SEC delays a crypto rule decision", "description": ""})
    assert "$" not in slides[1]["title"]


def test_render_six_slides(tmp_path: Path):
    paths = render_what_moved(
        {"title": "Fed holds rates. Bitcoin barely moved.", "description": "Officials left the target unchanged."},
        tmp_path,
        fetch_stock=False,
    )
    assert len(paths) == 6
    for path in paths:
        image = Image.open(path)
        assert image.size == (1080, 1350)
    caption = (tmp_path / "ig_carousel" / "caption.txt").read_text(encoding="utf-8")
    assert "YouTube" in caption
    assert carousel_caption({"title": "Fed holds rates"}) 



def test_instagram_feed_assets_six_slides(tmp_path, monkeypatch):
    from src.media import instagram_feed_image as feed

    monkeypatch.setattr(
        "src.media.ig_carousel.render_what_moved",
        lambda content, work_dir, fetch_stock=True: [
            Path(work_dir) / f"{i}.jpg" for i in range(6)
        ],
    )
    paths = feed.create_instagram_feed_assets("Hello", tmp_path, carousel=True)
    assert len(paths) == 6
    one = feed.create_instagram_feed_assets("Hello", tmp_path, carousel=False)
    assert len(one) == 1
