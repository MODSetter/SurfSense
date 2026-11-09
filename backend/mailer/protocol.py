"""Provider-agnostic transactional mail contract.

Everything above this module talks to ``Mailer`` and the two errors below; no
SMTP exception escapes the package, so changing how mail is sent never touches
a call site.

The payload is deliberately feature-agnostic. ``sender`` travels *on the
message* rather than being fixed on the sender object, because one SMTP
connection serves every feature and each one addresses its mail differently --
licenses from one address, account email from another. A sender baked into the
transport would make it a license mailer forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Attachment:
    """One file on a message. Base64 transfer encoding is the transport's job."""

    filename: str
    content: bytes
    # octet-stream, not text/plain: some clients render a text attachment
    # inline and mangle line endings, which corrupts a license file.
    content_type: str = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    """One transactional message, fully rendered and addressed."""

    to: str
    subject: str
    text_body: str
    # None falls back to SMTP_FROM. Features that want their own identity set
    # it; everything else inherits the deployment default.
    sender: str | None = None
    reply_to: str | None = None
    html_body: str | None = None
    attachments: tuple[Attachment, ...] = ()
    # Carried by the port and ignored by SMTP, which has no equivalent. It is
    # here so a future API-based transport can dedupe retries without any call
    # site changing.
    idempotency_key: str | None = None


@runtime_checkable
class Mailer(Protocol):
    """Sends one message, or raises one of the two errors below."""

    async def send(self, message: OutboundEmail) -> None: ...


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
