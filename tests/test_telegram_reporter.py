"""Tests for spystroke.telegram_reporter."""

import asyncio
from types import SimpleNamespace
from unittest import mock

import httpx
import pytest

from spystroke.telegram_reporter import (
    MAX_MESSAGE_LENGTH,
    TelegramReporter,
    split_message,
)


class TestSplitMessage:
    def test_short_message_unchanged(self):
        assert split_message("hello") == ["hello"]

    def test_empty_message(self):
        assert split_message("") == [""]

    def test_long_message_split_on_newlines(self):
        text = "\n".join(f"line {i} " + "x" * 100 for i in range(100))
        chunks = split_message(text, limit=1000)
        assert len(chunks) > 1
        assert all(len(c) <= 1000 for c in chunks)
        assert "".join(chunks) == text  # nothing lost or reordered

    def test_long_line_falls_back_to_hard_split(self):
        text = "A" * 9500
        chunks = split_message(text, limit=4000)
        assert all(len(c) <= 4000 for c in chunks)
        assert "".join(chunks) == text

    def test_chunks_respect_telegram_limit(self):
        text = "word " * 5000
        for chunk in split_message(text):
            assert len(chunk) <= MAX_MESSAGE_LENGTH


def _ok_response():
    return SimpleNamespace(status_code=200, json=lambda: {"ok": True}, text="")


def _error_response(status_code, payload=None, text=""):
    return SimpleNamespace(
        status_code=status_code, json=lambda: payload or {}, text=text
    )


class TestTelegramReporter:
    def test_send_success(self):
        client = mock.AsyncMock()
        client.post.return_value = _ok_response()

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=3
            )
            assert await reporter.send("hello") is True

        asyncio.run(scenario())
        client.post.assert_awaited_once()

    def test_send_chunks_long_messages(self):
        client = mock.AsyncMock()
        client.post.return_value = _ok_response()

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=3
            )
            assert await reporter.send("x" * 9000) is True

        asyncio.run(scenario())
        assert client.post.await_count == 3  # 9000 chars -> 3 chunks

    def test_retries_on_network_error_then_succeeds(self):
        client = mock.AsyncMock()
        client.post.side_effect = [httpx.ConnectError("boom"), _ok_response()]

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=3, base_backoff=0.01
            )
            assert await reporter.send("hello") is True

        asyncio.run(scenario())
        assert client.post.await_count == 2

    def test_permanent_error_fails_fast(self):
        client = mock.AsyncMock()
        client.post.return_value = _error_response(401, text="unauthorized")

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=5
            )
            assert await reporter.send("hello") is False

        asyncio.run(scenario())
        # Must not retry on configuration errors.
        assert client.post.await_count == 1

    def test_retry_on_429_respects_retry_after(self):
        client = mock.AsyncMock()
        client.post.side_effect = [
            _error_response(429, {"parameters": {"retry_after": 0}}),
            _ok_response(),
        ]

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=3
            )
            assert await reporter.send("hello") is True

        asyncio.run(scenario())
        assert client.post.await_count == 2

    def test_gives_up_after_max_retries(self):
        client = mock.AsyncMock()
        client.post.side_effect = httpx.ConnectError("always down")

        async def scenario():
            reporter = TelegramReporter(
                "token", "chat", client=client, max_retries=3, base_backoff=0.01
            )
            assert await reporter.send("hello") is False

        asyncio.run(scenario())
        assert client.post.await_count == 3

    def test_empty_message_does_not_send(self):
        client = mock.AsyncMock()

        async def scenario():
            reporter = TelegramReporter("token", "chat", client=client)
            assert await reporter.send("") is True

        asyncio.run(scenario())
        client.post.assert_not_awaited()
