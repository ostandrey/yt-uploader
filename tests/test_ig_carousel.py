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
    assert len(slides) == 4
    assert "$4.6B" in slides[1]["title"]
    assert slides[0]["kind"] == "hook"
    assert slides[-1]["kind"] == "watch"
    assert "bloomberg.com" in slides[-1]["meta"]
    blob = " ".join(f"{s.get('title', '')} {s.get('body', '')} {s.get('meta', '')}" for s in slides)
    assert "http" not in blob.lower()
    assert "CryptoFinanceDigest" not in blob


def test_what_moved_does_not_invent_money():
    slides = build_what_moved({"title": "SEC delays a crypto rule decision", "description": ""})
    assert "$" not in slides[1]["title"]
    assert slides[1]["kind"] == "fact"
    assert slides[1]["title"] == "SEC"


def test_what_moved_uses_date_not_echoed_headline():
    slides = build_what_moved(
        {
            "title": "CFTC to Meet on Crypto Regulations on Aug. 20",
            "description": (
                "The CFTC will hold a meeting for its Innovation Advisory Committee "
                "on Aug. 20 to address regulation related to crypto assets, "
                "artificial intelligence and prediction markets."
            ),
        }
    )
    assert len(slides) == 4
    assert slides[0]["kind"] == "hook"
    assert slides[1]["kind"] == "fact"
    assert "Aug" in slides[1]["title"]
    assert slides[1].get("kicker") == "When"
    assert "CFTC to Meet" not in slides[1]["title"]
    assert slides[0]["title"] != slides[1]["title"]
    body = slides[1].get("body") or ""
    assert not body.lower().endswith(" on")
    assert "CFTC to Meet on Crypto Regulations" in body
    context = slides[2]["title"]
    assert "Innovation Advisory Committee" in context
    assert "prediction" in context.lower()
    assert "Aug" not in context
    assert not context.lower().rstrip(".").endswith((" on", " to", " for", " of"))
    assert 12 <= len(context.split()) <= 22
    assert context.rstrip(".") != slides[0]["title"].rstrip(".")
    blob = " ".join(f"{s.get('title', '')} {s.get('body', '')}" for s in slides)
    assert "$" not in blob


def test_context_drops_url_and_does_not_echo_headline():
    slides = build_what_moved(
        {
            "title": "Goldman Sachs to acquire Neos for $2.25 billion in ETFs",
            "description": (
                "Neos Investments offers the Bitcoin High Income ETF and Ethereum High Income ETF. "
                "Source: The Block Read more: https://www.theblock.co/news/business/2026-08-12-goldman "
                "Follow @coinwirenews for daily crypto market moves."
            ),
            "source_link": "https://www.theblock.co/news/business/2026-08-12-goldman-sachs",
        }
    )
    assert len(slides) == 4
    assert "for in" not in (slides[1].get("body") or "").lower()
    assert "$2.25" in slides[1]["title"]
    context = slides[2]["title"]
    assert "http" not in context.lower()
    assert "theblock.co/news" not in context
    assert "Neos" in context
    assert slides[2]["title"] != slides[0]["title"]
    assert "coinwirenews" in (slides[3].get("body") or "").lower()
    assert "theblock.co" in (slides[3].get("meta") or "")
    caption = carousel_caption(
        {
            "title": "Goldman Sachs to acquire Neos for $2.25 billion in ETFs",
            "description": "https://www.theblock.co/news/business/foo Neos runs income ETFs.",
            "source_link": "https://www.theblock.co/x",
        }
    )
    assert "http" not in caption.lower()
    assert "theblock.co" in caption


def test_render_four_slides(tmp_path: Path):
    paths = render_what_moved(
        {"title": "Fed holds rates. Bitcoin barely moved.", "description": "Officials left the target unchanged."},
        tmp_path,
        fetch_stock=False,
    )
    assert len(paths) == 4
    for path in paths:
        image = Image.open(path)
        assert image.size == (1080, 1350)
    caption = (tmp_path / "ig_carousel" / "caption.txt").read_text(encoding="utf-8")
    assert "Swipe for context" in caption
    story = tmp_path / "ig_story" / "story.jpg"
    assert story.is_file()
    story_im = Image.open(story)
    assert story_im.size == (1080, 1920)
    assert carousel_caption({"title": "Fed holds rates"})


def test_carousel_caption_avoids_context_slide_echo():
    content = {
        "title": "SEC delays spot ETH ETF decision again",
        "description": (
            "The commission pushed the deadline after requesting more issuer docs. "
            "Staff asked for clearer custody language."
        ),
        "carousel_caption": (
            "The commission pushed the deadline after requesting more issuer docs. "
            "Staff asked for clearer custody language.\n\nSwipe for context."
        ),
    }
    slides = build_what_moved(content)
    context = next(
        (s["title"] for s in slides if s.get("kind") == "body"),
        "",
    )
    caption = carousel_caption(content)
    assert context
    assert "Swipe for context" in caption
    # If CONTEXT leaked into caption wholesale, first clause would repeat.
    first_ctx = context.split(".")[0].strip()
    if len(first_ctx) > 40:
        assert first_ctx not in caption


def test_context_prefers_novel_facts_not_thin_stub():
    """Headline-overlap used to kill long lines and leave a 6-word CONTEXT stub."""
    slides = build_what_moved(
        {
            "title": "Laser Digital gets Japan first crypto exchange approval in 4 years",
            "description": (
                "The firm is backed by Nomura. Laser Digital received a Type 1 license "
                "from Japan FSA, the first crypto exchange approval in four years amid "
                "tighter oversight."
            ),
        }
    )
    context = next(s["title"] for s in slides if (s.get("kicker") or "").lower() == "context")
    assert "Nomura" in context or "Type 1" in context or "FSA" in context
    assert len(context.split()) >= 12
    assert "outlet published" not in context.lower()


def test_instagram_feed_assets_four_slides(tmp_path, monkeypatch):
    from src.media import instagram_feed_image as feed

    monkeypatch.setattr(
        "src.media.ig_carousel.render_what_moved",
        lambda content, work_dir, fetch_stock=True: [Path(work_dir) / f"{i}.jpg" for i in range(4)],
    )
    paths = feed.create_instagram_feed_assets("Hello", tmp_path, carousel=True)
    assert len(paths) == 4
    one = feed.create_instagram_feed_assets("Hello", tmp_path, carousel=False)
    assert len(one) == 1
