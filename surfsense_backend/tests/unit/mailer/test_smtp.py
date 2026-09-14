"""The SMTP sender: MIME shape, configuration guards, and error mapping.

The error mapping is the whole reason the port has two errors: 4xx/5xx is a
protocol-level split that is identical at every provider, so callers never see
a vendor exception.
"""

from __future__ import annotations

import smtplib

import pytest

from app.mailer.protocol import (
    Attachment,
    MailerRejectedError,
    MailerUnavailableError,
    OutboundEmail,
)
from app.mailer.smtp import SmtpMailer, _build_mime

pytestmark = pytest.mark.unit


@pytest.fixture
def smtp_config(monkeypatch):
    from app.config import config

    monkeypatch.setattr(config, "SMTP_FROM", "licenses@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_REPLY_TO", "")
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "SMTP_USERNAME", "user")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(config, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(config, "SMTP_TIMEOUT_SECONDS", 5)
    return config


def _message() -> OutboundEmail:
    return OutboundEmail(
        to="buyer@example.com",
        subject="Your SurfSense license",
        text_body="body",
        attachments=(Attachment(filename="surfsense.lic", content=b"CERT"),),
    )


def test_mime_carries_the_license_as_a_binary_attachment(smtp_config):
    mime = _build_mime(_message(), sender="licenses@surfsense.test")

    assert mime["To"] == "buyer@example.com"
    assert mime["From"] == "licenses@surfsense.test"
    attachments = list(mime.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "surfsense.lic"
    assert attachments[0].get_content_type() == "application/octet-stream"
    assert attachments[0].get_payload(decode=True) == b"CERT"


def test_reply_to_travels_on_the_message(smtp_config):
    """Reply-To is per-feature, so it rides the message, not the sender."""
    from dataclasses import replace

    with_reply = _build_mime(
        replace(_message(), reply_to="support@surfsense.test"), sender="a@b.test"
    )
    without = _build_mime(_message(), sender="a@b.test")

    assert with_reply["Reply-To"] == "support@surfsense.test"
    assert without["Reply-To"] is None


def test_a_message_sender_overrides_the_deployment_default(smtp_config, monkeypatch):
    """One SMTP connection, many features, each with its own From."""
    from dataclasses import replace

    captured = {}
    monkeypatch.setattr(
        "app.mailer.smtp._send_blocking", lambda mime: captured.update(mime=mime)
    )

    import asyncio

    asyncio.run(
        SmtpMailer().send(replace(_message(), sender="licenses@surfsense.test"))
    )

    assert captured["mime"]["From"] == "licenses@surfsense.test"


def test_a_message_without_a_sender_falls_back_to_smtp_from(smtp_config, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.mailer.smtp._send_blocking", lambda mime: captured.update(mime=mime)
    )

    import asyncio

    asyncio.run(SmtpMailer().send(_message()))

    assert captured["mime"]["From"] == smtp_config.SMTP_FROM


def test_plaintext_with_credentials_is_refused(smtp_config, monkeypatch):
    """`none` must never put provider credentials on the wire in the clear."""
    monkeypatch.setattr(smtp_config, "SMTP_SECURITY", "none")

    with pytest.raises(ValueError, match="clear"):
        SmtpMailer()


def test_plaintext_without_credentials_is_allowed(smtp_config, monkeypatch):
    """A local relay like Mailpit takes no credentials and is a valid dev setup."""
    monkeypatch.setattr(smtp_config, "SMTP_SECURITY", "none")
    monkeypatch.setattr(smtp_config, "SMTP_USERNAME", "")
    monkeypatch.setattr(smtp_config, "SMTP_HOST", "localhost")

    assert SmtpMailer() is not None


def test_unknown_security_mode_is_refused(smtp_config, monkeypatch):
    monkeypatch.setattr(smtp_config, "SMTP_SECURITY", "ssl-maybe")

    with pytest.raises(ValueError, match="SMTP_SECURITY"):
        SmtpMailer()


def test_missing_from_address_is_refused(smtp_config, monkeypatch):
    monkeypatch.setattr(smtp_config, "SMTP_FROM", "")

    with pytest.raises(ValueError, match="SMTP_FROM"):
        SmtpMailer()


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (
            smtplib.SMTPAuthenticationError(535, b"bad credentials"),
            MailerUnavailableError,
        ),
        (
            smtplib.SMTPSenderRefused(553, b"unverified sender", "a@b.test"),
            MailerUnavailableError,
        ),
        (
            smtplib.SMTPRecipientsRefused({"x@y.test": (550, b"no such user")}),
            MailerRejectedError,
        ),
        (
            smtplib.SMTPRecipientsRefused({"x@y.test": (450, b"greylisted")}),
            MailerUnavailableError,
        ),
        (smtplib.SMTPResponseException(451, b"try later"), MailerUnavailableError),
        (smtplib.SMTPResponseException(552, b"too big"), MailerRejectedError),
        (smtplib.SMTPServerDisconnected("closed"), MailerUnavailableError),
        (smtplib.SMTPConnectError(421, b"unavailable"), MailerUnavailableError),
        (TimeoutError("timed out"), MailerUnavailableError),
        (OSError("dns"), MailerUnavailableError),
    ],
)
async def test_every_smtp_failure_maps_to_one_of_two_errors(
    smtp_config, monkeypatch, raised, expected
):
    def boom(_mime):
        raise raised

    monkeypatch.setattr("app.mailer.smtp._send_blocking", boom)

    with pytest.raises(expected):
        await SmtpMailer().send(_message())


async def test_successful_send_passes_the_rendered_mime_through(
    smtp_config, monkeypatch
):
    captured = {}

    def record(mime):
        captured["mime"] = mime

    monkeypatch.setattr("app.mailer.smtp._send_blocking", record)

    await SmtpMailer().send(_message())

    assert captured["mime"]["To"] == "buyer@example.com"
    assert captured["mime"]["Subject"] == "Your SurfSense license"
