"""Recording implementation of the mailer contract.

Mirrors ``fake_sandbox.py``: the whole license flow is testable with no mail
provider configured, which is the point of the adapter.
"""

from __future__ import annotations

from app.mailer.protocol import MailerError, OutboundEmail


class FakeMailer:
    """Records every message; optionally raises a chosen error instead."""

    def __init__(self, *, raises: MailerError | None = None) -> None:
        self.sent: list[OutboundEmail] = []
        self.raises = raises

    async def send(self, message: OutboundEmail) -> None:
        if self.raises is not None:
            raise self.raises
        self.sent.append(message)

    @property
    def recipients(self) -> list[str]:
        return [message.to for message in self.sent]

    def only(self) -> OutboundEmail:
        assert len(self.sent) == 1, f"expected exactly one email, got {len(self.sent)}"
        return self.sent[0]
