"""SMTP transport.

SMTP is chosen because it is the only *universal* interface: Resend, Postmark,
SendGrid, Mailgun, SES and Brevo all expose it and all reduce to
host/port/username/password. Picking a vendor is therefore filling in strings,
not writing code -- which is what lets the vendor decision be deferred.

Implementation is stdlib (``email.message`` + ``smtplib``) run through
``asyncio.to_thread``, so this adds no dependency. ``aiosmtplib`` was the
alternative; zero dependencies won over avoiding one threadpool hop at license
volume.

One connection per send. Pooled SMTP connections go stale and servers drop idle
sessions, so the reconnect logic would cost more than it saves here.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import config

from ..protocol import (
    LicenseEmail,
    MailerRejectedError,
    MailerUnavailableError,
)

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def _build_mime(
    message: LicenseEmail, *, sender: str, reply_to: str | None
) -> EmailMessage:
    mime = EmailMessage()
    mime["From"] = sender
    mime["To"] = message.to
    mime["Subject"] = message.subject
    if reply_to:
        mime["Reply-To"] = reply_to

    mime.set_content(message.text_body)
    if message.html_body:
        mime.add_alternative(message.html_body, subtype="html")

    for attachment in message.attachments:
        maintype, _, subtype = attachment.content_type.partition("/")
        mime.add_attachment(
            attachment.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
        )
    return mime


def _connect() -> smtplib.SMTP:
    host = config.LICENSE_MAIL_SMTP_HOST
    port = config.LICENSE_MAIL_SMTP_PORT
    timeout = config.LICENSE_MAIL_TIMEOUT_SECONDS
    security = config.LICENSE_MAIL_SMTP_SECURITY

    if security == "tls":
        return smtplib.SMTP_SSL(host, port, timeout=timeout)

    client = smtplib.SMTP(host, port, timeout=timeout)
    if security == "starttls":
        client.ehlo()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
    return client


def _send_blocking(mime: EmailMessage) -> None:
    client = _connect()
    try:
        username = config.LICENSE_MAIL_SMTP_USERNAME
        password = config.LICENSE_MAIL_SMTP_PASSWORD
        if username:
            client.login(username, password or "")
        client.send_message(mime)
    finally:
        try:
            client.quit()
        except smtplib.SMTPException:
            # A server that hangs up before QUIT has still accepted the
            # message; failing here would report a send that succeeded.
            client.close()


class SmtpMailer:
    """Sends over SMTP, translating every failure into the port's two errors."""

    def __init__(self) -> None:
        sender = config.LICENSE_MAIL_FROM
        if not sender:
            raise ValueError("LICENSE_MAIL_FROM is required when the mailer is smtp")
        if not config.LICENSE_MAIL_SMTP_HOST:
            raise ValueError(
                "LICENSE_MAIL_SMTP_HOST is required when the mailer is smtp"
            )

        security = config.LICENSE_MAIL_SMTP_SECURITY
        if security not in {"starttls", "tls", "none"}:
            raise ValueError(
                f"Unknown LICENSE_MAIL_SMTP_SECURITY {security!r}. "
                "Expected one of: starttls, tls, none"
            )
        # Explicit rather than inferred from the port: 465 is implicit TLS and
        # 587 is STARTTLS, and guessing from the port number is the classic
        # source of "it hangs forever with no error".
        if security == "none" and config.LICENSE_MAIL_SMTP_USERNAME:
            raise ValueError(
                "LICENSE_MAIL_SMTP_SECURITY=none refuses to send credentials in "
                "the clear. Use starttls or tls, or drop the username for a "
                "local relay."
            )
        if security == "none" and config.LICENSE_MAIL_SMTP_HOST not in _LOOPBACK_HOSTS:
            logger.warning(
                "LICENSE_MAIL_SMTP_SECURITY=none to non-loopback host %s: license "
                "files will cross the network unencrypted.",
                config.LICENSE_MAIL_SMTP_HOST,
            )

        self._sender = sender
        self._reply_to = config.LICENSE_MAIL_REPLY_TO or None

    async def send(self, message: LicenseEmail) -> None:
        mime = _build_mime(message, sender=self._sender, reply_to=self._reply_to)
        try:
            await asyncio.to_thread(_send_blocking, mime)
        except smtplib.SMTPAuthenticationError as exc:
            # Our misconfiguration, not the recipient's address. Never surface
            # this as a rejected email.
            raise MailerUnavailableError(
                "SMTP authentication failed; check the provider credentials"
            ) from exc
        except smtplib.SMTPSenderRefused as exc:
            # Almost always an unverified From domain -- also our problem.
            raise MailerUnavailableError(
                f"SMTP server refused the sender {self._sender!r}"
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [code for code, _ in exc.recipients.values()]
            if codes and all(code >= 500 for code in codes):
                raise MailerRejectedError(
                    f"Recipient refused by the mail server: {codes}"
                ) from exc
            raise MailerUnavailableError(
                f"Recipient temporarily refused: {codes}"
            ) from exc
        except smtplib.SMTPResponseException as exc:
            if exc.smtp_code >= 500:
                raise MailerRejectedError(
                    f"Mail server permanently refused the message ({exc.smtp_code})"
                ) from exc
            raise MailerUnavailableError(
                f"Mail server temporarily refused the message ({exc.smtp_code})"
            ) from exc
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            # Connect failure, disconnect, DNS, timeout.
            raise MailerUnavailableError(
                f"Could not reach the mail server: {exc}"
            ) from exc
