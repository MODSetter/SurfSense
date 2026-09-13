"""Transactional mail for the license flows.

The vendor is deliberately not decided: the transport is SMTP, which every
transactional provider exposes, so choosing one later is configuration rather
than code. See ``plans/community-local/portal/01-license-routes.md``.
"""

from .factory import build_mailer, get_mailer, is_mail_enabled, reset_mailer
from .protocol import (
    Attachment,
    LicenseEmail,
    LicenseEmailKind,
    Mailer,
    MailerError,
    MailerRejectedError,
    MailerUnavailableError,
)
from .templates import build_license_email

__all__ = [
    "Attachment",
    "LicenseEmail",
    "LicenseEmailKind",
    "Mailer",
    "MailerError",
    "MailerRejectedError",
    "MailerUnavailableError",
    "build_license_email",
    "build_mailer",
    "get_mailer",
    "is_mail_enabled",
    "reset_mailer",
]
