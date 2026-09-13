"""SMTP transport: MIME shape, configuration guards, and error mapping.

The error mapping is the whole reason the port has two errors: 4xx/5xx is a
protocol-level split that is identical at every provider, so callers never see
a vendor exception.
"""

from __future__ import annotations

import smtplib

import pytest

from app.mailer.protocol import (
    Attachment,
    LicenseEmail,
    MailerRejectedError,
    MailerUnavailableError,
)
from app.mailer.transports.smtp import SmtpMailer, _build_mime

pytestmark = pytest.mark.unit


@pytest.fixture
def smtp_config(monkeypatch):
    from app.config import config

    monkeypatch.setattr(config, "LICENSE_MAIL_FROM", "licenses@surfsense.test")
    monkeypatch.setattr(config, "LICENSE_MAIL_REPLY_TO", "")
    monkeypatch.setattr(config, "LICENSE_MAIL_SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(config, "LICENSE_MAIL_SMTP_PORT", 587)
    monkeypatch.setattr(config, "LICENSE_MAIL_SMTP_USERNAME", "user")
    monkeypatch.setattr(config, "LICENSE_MAIL_SMTP_PASSWORD", "secret")
    monkeypatch.setattr(config, "LICENSE_MAIL_SMTP_SECURITY", "starttls")
    monkeypatch.setattr(config, "LICENSE_MAIL_TIMEOUT_SECONDS", 5)
    return config


def _message() -> LicenseEmail:
    return LicenseEmail(
        to="buyer@example.com",
        kind="purchase",
        subject="Your SurfSense license",
        text_body="body",
        attachments=(Attachment(filename="surfsense.lic", content=b"CERT"),),
    )


def test_mime_carries_the_license_as_a_binary_attachment(smtp_config):
    mime = _build_mime(_message(), sender="licenses@surfsense.test", reply_to=None)

    assert mime["To"] == "buyer@example.com"
    assert mime["From"] == "licenses@surfsense.test"
    attachments = list(mime.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "surfsense.lic"
    assert attachments[0].get_content_type() == "application/octet-stream"
    assert attachments[0].get_payload(decode=True) == b"CERT"


def test_reply_to_is_set_only_when_configured(smtp_config):
    with_reply = _build_mime(
        _message(), sender="a@b.test", reply_to="support@surfsense.test"
    )
    without = _build_mime(_message(), sender="a@b.test", reply_to=None)

    assert with_reply["Reply-To"] == "support@surfsense.test"
    assert without["Reply-To"] is None


def test_plaintext_with_credentials_is_refused(smtp_config, monkeypatch):
    """`none` must never put provider credentials on the wire in the clear."""
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_SMTP_SECURITY", "none")

    with pytest.raises(ValueError, match="clear"):
        SmtpMailer()


def test_plaintext_without_credentials_is_allowed(smtp_config, monkeypatch):
    """A local relay like Mailpit takes no credentials and is a valid dev setup."""
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_SMTP_SECURITY", "none")
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_SMTP_USERNAME", "")
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_SMTP_HOST", "localhost")

    assert SmtpMailer() is not None


def test_unknown_security_mode_is_refused(smtp_config, monkeypatch):
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_SMTP_SECURITY", "ssl-maybe")

    with pytest.raises(ValueError, match="LICENSE_MAIL_SMTP_SECURITY"):
        SmtpMailer()


def test_missing_from_address_is_refused(smtp_config, monkeypatch):
    monkeypatch.setattr(smtp_config, "LICENSE_MAIL_FROM", "")

    with pytest.raises(ValueError, match="LICENSE_MAIL_FROM"):
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

    monkeypatch.setattr("app.mailer.transports.smtp._send_blocking", boom)

    with pytest.raises(expected):
        await SmtpMailer().send(_message())


async def test_successful_send_passes_the_rendered_mime_through(
    smtp_config, monkeypatch
):
    captured = {}

    def record(mime):
        captured["mime"] = mime

    monkeypatch.setattr("app.mailer.transports.smtp._send_blocking", record)

    await SmtpMailer().send(_message())

    assert captured["mime"]["To"] == "buyer@example.com"
    assert captured["mime"]["Subject"] == "Your SurfSense license"
