"""TikTok publish wait must not treat TIMEOUT / error JSON as success."""

from __future__ import annotations


def test_tiktok_wait_raises_on_timeout(monkeypatch):
    from src.publishers.tiktok_publisher import TikTokPublisher

    pub = TikTokPublisher.__new__(TikTokPublisher)

    class FakeResp:
        content = b'{"data":{"status":"PROCESSING_UPLOAD"}}'

        def json(self):
            return {"data": {"status": "PROCESSING_UPLOAD"}}

    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 100.0 if calls["n"] < 3 else 999.0

    monkeypatch.setattr("src.publishers.tiktok_publisher.time.time", fake_time)
    monkeypatch.setattr("src.publishers.tiktok_publisher.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "src.ops.retry.call_with_retry",
        lambda fn, **k: FakeResp(),
    )
    try:
        pub._wait_publish("pub-1", max_wait_sec=1)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "timeout" in str(exc).lower()


def test_tiktok_wait_raises_on_error_body(monkeypatch):
    from src.publishers.tiktok_publisher import TikTokPublisher

    pub = TikTokPublisher.__new__(TikTokPublisher)

    class FakeResp:
        content = b'{"error":{"code":"invalid_token","message":"bad"}}'

        def json(self):
            return {"error": {"code": "invalid_token", "message": "bad"}}

    monkeypatch.setattr("src.publishers.tiktok_publisher.time.time", lambda: 1.0)
    monkeypatch.setattr("src.publishers.tiktok_publisher.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "src.ops.retry.call_with_retry",
        lambda fn, **k: FakeResp(),
    )
    try:
        pub._wait_publish("pub-1", max_wait_sec=30)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "invalid_token" in str(exc) or "error" in str(exc).lower()
