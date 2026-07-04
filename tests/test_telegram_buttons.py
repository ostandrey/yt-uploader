"""Inline keyboard helpers for owner bot notifications."""

from src.publishers.telegram_publisher import control_keyboard, normalize_keyboard


def test_normalize_single_row():
    row = [{"text": "Read", "url": "https://example.com"}]
    assert normalize_keyboard(row) == [row]


def test_normalize_multi_row():
    rows = [
        [{"text": "A", "callback_data": "a"}],
        [{"text": "B", "callback_data": "b"}],
    ]
    assert normalize_keyboard(rows) == rows


def test_control_keyboard_without_video():
    rows = control_keyboard()
    assert len(rows) == 1
    labels = [b["text"] for b in rows[0]]
    assert labels == ["Status", "Pause AP", "Resume AP"]
    assert all("callback_data" in b for b in rows[0])


def test_control_keyboard_with_video():
    rows = control_keyboard("abc123XYZ01")
    assert len(rows) == 2
    assert rows[0][0]["callback_data"] == "cw:pub:abc123XYZ01"
    assert rows[0][1]["callback_data"] == "cw:hold:abc123XYZ01"
