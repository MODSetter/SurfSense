"""The two record shapes a cohort is built from, held only in memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Trial:
    licence_id: str
    created: date
    folded_email: str


@dataclass(slots=True)
class Purchase:
    paid_on: date
    # Folded: the licence's address, the address typed at checkout and the
    # Stripe customer's, since a buyer can pay from another address.
    folded_emails: set[str] = field(default_factory=set)
    refunded: bool = False
    checkout_session_id: str | None = None
