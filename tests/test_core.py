"""Tests for spystroke.core: key formatting and the thread-safe buffer."""

import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from spystroke.core import KeystrokeBuffer, KeyListener, format_key


# ---------------------------------------------------------------------------
# format_key
# ---------------------------------------------------------------------------

def _char_key(char):
    """Mimic pynput KeyCode with a character."""
    return SimpleNamespace(char=char, vk=None, name=None)


def _vk_key(vk):
    """Mimic pynput KeyCode without a character (media keys etc.)."""
    return SimpleNamespace(char=None, vk=vk, name=None)


def _special_key(name):
    """Mimic a pynput Key enum member."""
    return SimpleNamespace(char=None, vk=None, name=name)


class TestFormatKey:
    @pytest.mark.parametrize(
        "key,expected",
        [
            (_char_key("a"), "a"),
            (_char_key("1"), "1"),
            (_char_key(" "), " "),
            (_char_key("\r"), "\n"),  # carriage return -> newline
            (_special_key("space"), " "),
            (_special_key("enter"), "\n"),
            (_special_key("tab"), "\t"),
            (_special_key("ctrl_l"), "[CTRL] "),
            (_special_key("ctrl_r"), "[CTRL] "),
            (_special_key("shift"), "[SHIFT] "),
            (_special_key("alt_gr"), "[ALT_GR] "),
            (_special_key("backspace"), "[BACKSPACE] "),
            (_special_key("up"), "[UP] "),
            (_special_key("f5"), "[F5] "),
            (_special_key("f12"), "[F12] "),
            (_special_key("print_screen"), "[PRINT_SCREEN] "),
            (_vk_key(173), "[VK:173] "),
        ],
    )
    def test_known_keys(self, key, expected):
        assert format_key(key) == expected

    def test_unknown_special_key_uses_name(self):
        assert format_key(_special_key("media_play_pause")) == "[MEDIA_PLAY_PAUSE] "

    def test_none_character_does_not_raise(self):
        # The original code crashed on this (TypeError: cannot concat None).
        assert format_key(_char_key(None)) == "[UNKNOWN] "

    def test_unknown_object_does_not_raise(self):
        assert format_key(object()) == "[UNKNOWN] "
        assert format_key(None) == "[UNKNOWN] "


# ---------------------------------------------------------------------------
# KeystrokeBuffer
# ---------------------------------------------------------------------------

class TestKeystrokeBuffer:
    def test_append_and_drain(self):
        buf = KeystrokeBuffer()
        buf.append("a")
        buf.append("b")
        buf.append("c")
        assert buf.drain() == "abc"
        assert buf.drain() == ""  # drained buffer is empty

    def test_bool_and_size(self):
        buf = KeystrokeBuffer()
        assert not buf
        assert buf.size == 0
        buf.append("hello")
        assert buf
        assert buf.size == 5
        buf.drain()
        assert not buf

    def test_empty_append_is_ignored(self):
        buf = KeystrokeBuffer()
        buf.append("")
        buf.append(None)  # type: ignore[arg-type] - defensive
        assert buf.drain() == ""

    def test_drain_is_atomic(self):
        """Concurrent writers must never lose or interleave data."""
        buf = KeystrokeBuffer()
        results = []

        def writer(prefix: str):
            for i in range(100):
                buf.append(f"{prefix}{i},")

        threads = [
            threading.Thread(target=writer, args=("A",)),
            threading.Thread(target=writer, args=("B",)),
            threading.Thread(target=writer, args=("C",)),
        ]
        for t in threads:
            t.start()

        # Drain concurrently while writers are still running.
        while any(t.is_alive() for t in threads):
            chunk = buf.drain()
            if chunk:
                results.append(chunk)
            time.sleep(0.001)
        for t in threads:
            t.join()

        chunk = buf.drain()
        if chunk:
            results.append(chunk)

        joined = "".join(results)
        assert joined.count("A") == 100
        assert joined.count("B") == 100
        assert joined.count("C") == 100
        # Every token must be complete (no torn writes).
        for token in joined.split(","):
            if not token:
                continue
            assert token[0] in "ABC" and token[1:].isdigit()


# ---------------------------------------------------------------------------
# KeyListener
# ---------------------------------------------------------------------------

class TestKeyListener:
    def test_start_creates_listener_and_formats_keys(self):
        fake_listener = mock.Mock()
        fake_listener.start = mock.Mock()
        fake_listener.stop = mock.Mock()
        fake_listener.join = mock.Mock()

        captured = {}

        def fake_factory(**kwargs):
            captured.update(kwargs)
            return fake_listener

        with mock.patch("spystroke.core._keyboard.Listener", side_effect=fake_factory):
            listener = KeyListener()
            assert listener.start() is True
            assert listener.running
            # Calling start twice must be a no-op.
            assert listener.start() is False

            # Simulate key presses through the registered callback.
            on_press = captured["on_press"]
            on_press(_char_key("h"))
            on_press(_char_key("i"))
            on_press(_special_key("space"))
            on_press(_special_key("enter"))
            on_press(_char_key(None))  # must not raise, formats as unknown

            assert listener.buffer.drain() == "hi \n[UNKNOWN] "

            listener.stop()
            assert not listener.running
            fake_listener.stop.assert_called_once()
            fake_listener.join.assert_called_once()

    def test_stop_without_start_is_safe(self):
        listener = KeyListener()
        listener.stop()  # must not raise
        assert not listener.running

    def test_error_hook_is_called_on_callback_failure(self):
        fake_listener = mock.Mock()
        with mock.patch(
            "spystroke.core._keyboard.Listener", side_effect=lambda **kw: fake_listener
        ):
            err = mock.Mock()
            listener = KeyListener(on_error=err)
            listener.start()
            # Force an exception inside the callback: it must be caught,
            # logged and reported to the error hook, not crash the thread.
            with mock.patch(
                "spystroke.core.format_key", side_effect=RuntimeError("boom")
            ):
                listener._handle_press(_char_key("x"))
            err.assert_called_once()
            listener.stop()
