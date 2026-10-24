"""What Stripe adds to a purchase: the addresses it was paid from, and refunds.

Read-only, one session lookup per purchase: a restricted key that reads
Checkout Sessions, Customers, PaymentIntents and Charges is enough.
"""

from __future__ import annotations

from typing import Any

from license.email.address import fold_email

from .models import Purchase


def add_stripe_view(purchases: list[Purchase], stripe_client: Any) -> int:
    """Fill in Stripe's addresses and refunds; returns how many lookups failed."""
    failures = 0
    for purchase in purchases:
        if not purchase.checkout_session_id:
            continue
        try:
            session = stripe_client.v1.checkout.sessions.retrieve(
                purchase.checkout_session_id,
                params={"expand": ["customer", "payment_intent.latest_charge"]},
            )
        except Exception:
            # Counted, never logged with the id: the report prints no identifier.
            failures += 1
            continue
        for email in (_checkout_email(session), _customer_email(session)):
            if email:
                purchase.folded_emails.add(fold_email(email))
        if _fully_refunded(session):
            purchase.refunded = True
    return failures


def _checkout_email(session: Any) -> str | None:
    details = getattr(session, "customer_details", None)
    if isinstance(details, dict):
        return details.get("email")
    return getattr(details, "email", None)


def _customer_email(session: Any) -> str | None:
    # Unexpanded, the customer is only its id.
    customer = getattr(session, "customer", None)
    return None if isinstance(customer, str) else getattr(customer, "email", None)


def _fully_refunded(session: Any) -> bool:
    """A full refund only, as ``purchase.py`` suspends on; a partial one is goodwill."""
    intent = getattr(session, "payment_intent", None)
    charge = getattr(intent, "latest_charge", None)
    if charge is None or isinstance(charge, str):
        return False
    if getattr(charge, "refunded", False):
        return True
    amount = getattr(charge, "amount", None)
    refunded = getattr(charge, "amount_refunded", None)
    return (
        isinstance(amount, int) and isinstance(refunded, int) and refunded >= amount > 0
    )
