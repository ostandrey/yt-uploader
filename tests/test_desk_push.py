"""Desk Web Push helpers."""

from src.desk import push


def test_vapid_generate_and_subscribe(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "STORAGE", tmp_path)
    monkeypatch.setattr(push, "VAPID_FILE", tmp_path / "vapid.json")
    monkeypatch.setattr(push, "SUBS_FILE", tmp_path / "subs.json")
    monkeypatch.delenv("DESK_VAPID_PUBLIC", raising=False)
    monkeypatch.delenv("DESK_VAPID_PRIVATE", raising=False)
    key = push.public_key()
    assert key
    assert push.push_configured()
    push.save_subscription(
        {
            "endpoint": "https://example.com/push/1",
            "keys": {"p256dh": "a", "auth": "b"},
        }
    )
    subs = push.load_subscriptions()
    assert len(subs) == 1
    assert subs[0]["endpoint"].endswith("/1")
