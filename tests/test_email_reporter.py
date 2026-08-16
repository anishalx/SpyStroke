"""Tests for spystroke.email_reporter."""

import smtplib
from unittest import mock

import pytest

from spystroke.email_reporter import EmailReporter


def _fake_server():
    server = mock.Mock()
    server.ehlo = mock.Mock()
    server.starttls = mock.Mock()
    server.login = mock.Mock()
    server.send_message = mock.Mock()
    server.quit = mock.Mock()
    return server


class TestEmailReporter:
    def test_send_success_with_starttls(self):
        server = _fake_server()
        with mock.patch("smtplib.SMTP", return_value=server) as smtp_cls:
            reporter = EmailReporter("me@example.com", "secret")
            assert reporter.send("subject", "body") is True

        smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=15.0)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("me@example.com", "secret")
        server.send_message.assert_called_once()
        message = server.send_message.call_args.args[0]
        assert message["Subject"] == "subject"
        assert message["From"] == "me@example.com"
        assert message["To"] == "me@example.com"

    def test_send_success_with_implicit_tls(self):
        server = _fake_server()
        with mock.patch("smtplib.SMTP_SSL", return_value=server) as ssl_cls:
            reporter = EmailReporter(
                "me@example.com", "secret", smtp_port=465, use_starttls=False
            )
            assert reporter.send("subject", "body") is True

        ssl_cls.assert_called_once()
        server.starttls.assert_not_called()

    def test_send_uses_receiver_when_provided(self):
        server = _fake_server()
        with mock.patch("smtplib.SMTP", return_value=server):
            reporter = EmailReporter("me@example.com", "secret", receiver="them@x.com")
            reporter.send("subject", "body")
        message = server.send_message.call_args.args[0]
        assert message["To"] == "them@x.com"

    def test_auth_error_fails_fast(self):
        server = _fake_server()
        server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad creds")
        with mock.patch("smtplib.SMTP", return_value=server):
            reporter = EmailReporter(
                "me@example.com", "wrong", max_retries=4, base_backoff=0.01
            )
            assert reporter.send("subject", "body") is False
        # Must not retry on auth failures.
        assert server.login.call_count == 1

    def test_transient_error_retries_then_succeeds(self):
        server = _fake_server()
        server.send_message.side_effect = [
            smtplib.SMTPServerDisconnected("connection lost"),
            None,
        ]
        with mock.patch("smtplib.SMTP", return_value=server):
            reporter = EmailReporter(
                "me@example.com", "secret", max_retries=3, base_backoff=0.01
            )
            assert reporter.send("subject", "body") is True
        assert server.send_message.call_count == 2

    def test_gives_up_after_max_retries(self):
        server = _fake_server()
        server.send_message.side_effect = OSError("network down")
        with mock.patch("smtplib.SMTP", return_value=server):
            reporter = EmailReporter(
                "me@example.com", "secret", max_retries=3, base_backoff=0.01
            )
            assert reporter.send("subject", "body") is False
        assert server.send_message.call_count == 3

    def test_empty_body_does_not_send(self):
        with mock.patch("smtplib.SMTP") as smtp_cls:
            reporter = EmailReporter("me@example.com", "secret")
            assert reporter.send("subject", "") is True
        smtp_cls.assert_not_called()

    def test_quit_failure_is_survived(self):
        server = _fake_server()
        server.quit.side_effect = smtplib.SMTPServerDisconnected("gone")
        with mock.patch("smtplib.SMTP", return_value=server):
            reporter = EmailReporter("me@example.com", "secret")
            assert reporter.send("subject", "body") is True
