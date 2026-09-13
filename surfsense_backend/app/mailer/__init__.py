"""Transactional email for the backend.

The transport is SMTP, which every transactional provider exposes, so choosing
a vendor is configuration rather than code. Licenses are the only caller today;
the connection is deployment-wide so account email can join it without
rewiring. See ``plans/community-local/portal/01-license-routes.md``.
"""

from .factory import build_mailer, get_mailer, is_mail_enabled, reset_mailer
from .protocol import (
    Attachment,
    Mailer,
    MailerError,
    MailerRejectedError,
    MailerUnavailableError,
    OutboundEmail,
)
from .templates import LicenseEmailKind, build_license_email

__all__ = [
    "Attachment",
    "LicenseEmailKind",
    "Mailer",
    "MailerError",
    "MailerRejectedError",
    "MailerUnavailableError",
    "OutboundEmail",
    "build_license_email",
    "build_mailer",
    "get_mailer",
    "is_mail_enabled",
    "reset_mailer",
]
