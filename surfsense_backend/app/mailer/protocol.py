"""Provider-agnostic transactional mail contract.

Only the license flows use this today. Everything above this module talks to
``Mailer`` and the two errors below; no transport exception escapes the
package, so swapping how mail is sent never touches a call site.

The payload models the *license email domain*, not SMTP: subjects and bodies
are built on our side (``templates.py``) so a provider change is never a copy
migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

LicenseEmailKind = Literal["purchase", "resend", "trial"]


@dataclass(frozen=True, slots=True)
class Attachment:
    """One file on a message. Base64 transfer encoding is the provider's job."""

    filename: str
    content: bytes
    # octet-stream, not text/plain: some clients render a text attachment
    # inline and mangle line endings, which corrupts a license file.
    content_type: str = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class LicenseEmail:
    """One transactional message, fully rendered."""

    to: str
    kind: LicenseEmailKind
    subject: str
    text_body: str
    html_body: str | None = None
    attachments: tuple[Attachment, ...] = ()
    # Carried by the port and ignored by SMTP, which has no equivalent. It is
    # here so a future API-based transport can dedupe retries without any call
    # site changing.
    idempotency_key: str | None = None


@runtime_checkable
class Mailer(Protocol):
    """Sends one message, or raises one of the two errors below."""

    async def send(self, message: LicenseEmail) -> None: ...


class MailerError(RuntimeError):
    """Base for every failure this package reports."""


class MailerUnavailableError(MailerError):
    """Transient, or our own misconfiguration. Never the recipient's fault.

    Covers connect failures, timeouts, SMTP 4xx, authentication failures and a
    refused sender. Callers may retry and must not tell the user their address
    was rejected.
    """


class MailerRejectedError(MailerError):
    """Permanent: the server refused this recipient during the conversation.

    Only in-conversation 5xx refusals land here. A hard bounce arrives after a
    250 accept, so this never catches every bad address -- callers promise
    "sent", not "delivered".
    """
