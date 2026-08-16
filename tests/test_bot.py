"""Integration tests for the Telegram bot wiring (SpyStrokeBot)."""

import asyncio
from unittest import mock

from spystroke.config import TelegramConfig
from spystroke.core import KeystrokeBuffer

# Import the entry module the same way it is loaded in production.
import importlib.util
import os
import sys

_SPEC = importlib.util.spec_from_file_location(
    "tbot_entry", os.path.join(os.path.dirname(__file__), "..", "telegram", "bot.py")
)
_tbot = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_tbot)

SpyStrokeBot = _tbot.SpyStrokeBot


class _FakeListener:
    """Minimal stand-in for KeyListener used by the bot."""

    def __init__(self):
        self.buffer = KeystrokeBuffer()
        self.running = False

    def start(self):
        self.running = True
        return True

    def stop(self):
        self.running = False


def _make_bot(interval=0.01):
    config = TelegramConfig(bot_token="token", chat_id="chat", interval=interval)
    bot = SpyStrokeBot(config)
    bot.listener = _FakeListener()
    bot.reporter = mock.AsyncMock()
    return bot


class TestSpyStrokeBot:
    def test_report_loop_drains_buffer_and_sends(self):
        bot = _make_bot(interval=0.01)
        bot.listener.buffer.append("typed text")

        async def scenario():
            task = asyncio.create_task(bot._report_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(scenario())
        bot.reporter.send.assert_awaited_once_with("typed text")
        assert bot.listener.buffer.size == 0  # drained after send

    def test_report_loop_skips_empty_buffer(self):
        bot = _make_bot(interval=0.01)

        async def scenario():
            task = asyncio.create_task(bot._report_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(scenario())
        bot.reporter.send.assert_not_awaited()

    def test_start_and_stop_logging(self):
        bot = _make_bot()

        async def scenario():
            assert await bot._start_logging() is True
            assert bot.listener.running
            # Starting again is a no-op.
            assert await bot._start_logging() is False
            await bot._stop_logging()
            assert not bot.listener.running

        asyncio.run(scenario())

    def test_status_command_reports_state(self):
        bot = _make_bot()
        update = mock.Mock()
        update.message.reply_text = mock.AsyncMock()

        async def scenario():
            await bot._cmd_status(update, mock.Mock())
            text = update.message.reply_text.await_args.args[0]
            assert "stopped" in text

        asyncio.run(scenario())
