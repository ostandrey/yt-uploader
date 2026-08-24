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
    info = push.subscription_debug_info(subs[0])
    assert info["has_endpoint"] is True
    assert info["has_p256dh"] is True
    assert info["has_auth"] is True
    assert push.vapid_source() in {"file", "generated"}


def test_notify_without_subs_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "STORAGE", tmp_path)
    monkeypatch.setattr(push, "VAPID_FILE", tmp_path / "vapid.json")
    monkeypatch.setattr(push, "SUBS_FILE", tmp_path / "subs.json")
    monkeypatch.delenv("DESK_VAPID_PUBLIC", raising=False)
    monkeypatch.delenv("DESK_VAPID_PRIVATE", raising=False)
    assert push.public_key()
    alerts: list[tuple] = []
    monkeypatch.setattr(
        push,
        "_alert_push_miss",
        lambda *a, **k: alerts.append((a, k)),
    )
    result = push.notify_desk_push("t", "b", tag="coin-wire-server-test")
    assert result["sent"] == 0
    assert result["reason"] == "no_subscriptions"
    # Still invoked from notify path; alert itself no-ops for no_subscriptions.
    assert alerts


def test_alert_push_miss_skips_no_subscriptions(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "STORAGE", tmp_path)
    called = []

    class FakePub:
        bot_token = "x"
        notify_chat_id = "1"

        def notify_owner(self, text, buttons=None):
            called.append(text)

    monkeypatch.setattr(
        "src.publishers.telegram_publisher.TelegramPublisher",
        FakePub,
    )
    push._alert_push_miss(
        "Short ready",
        "body",
        {"reason": "no_subscriptions", "subs": None, "failed": 0},
    )
    assert called == []
