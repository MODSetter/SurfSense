"""Pure presentation logic for auto-reload-failure notifications."""

from __future__ import annotations

from datetime import UTC, datetime


def operation_id(payment_intent_id: str) -> str:
    """Build a unique id for an auto-reload-failure notification.

    Keyed on the failed PaymentIntent so retries of the same charge collapse
    into a single inbox item rather than spamming the user.
    """
    if payment_intent_id:
        return f"auto_reload_failed_{payment_intent_id}"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    return f"auto_reload_failed_{timestamp}"


def summary(amount_micros: int, reason: str | None) -> tuple[str, str]:
    """Compute the title and message for a failed off-session auto-reload charge."""
    amount_usd = max(0, amount_micros) / 1_000_000
    title = "Auto-reload failed"
    base = (
        f"We couldn't automatically add ${amount_usd:.2f} of credit because your "
        "saved card was declined. Auto-reload has been turned off — update your "
        "card and re-enable it to keep topping up automatically."
    )
    if reason:
        base = f"{base} (Reason: {reason}.)"
    return title, base
