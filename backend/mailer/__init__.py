"""Transactional email for the backend.

The transport is SMTP, which every transactional provider exposes, so choosing
a vendor is configuration rather than code. The connection is deployment-wide;
each feature builds its own messages and stamps its own sender on them, so
nothing here knows what any of them are for.
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

__all__ = [
    "Attachment",
    "Mailer",
    "MailerError",
    "MailerRejectedError",
    "MailerUnavailableError",
    "OutboundEmail",
    "build_mailer",
    "get_mailer",
    "is_mail_enabled",
    "reset_mailer",
]
