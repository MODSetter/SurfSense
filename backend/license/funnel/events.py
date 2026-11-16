"""Personless funnel events: ``license_trial_issued`` and ``license_purchased``.

Each event gets a fresh random distinct id and ``$process_person_profile``
false, so no two events join into a person and none joins a browser. The
properties are the whole payload: never the email, the licence id or key,
the Stripe customer or session.
"""

from __future__ import annotations

import uuid
from typing import Any

from license import analytics as ph_analytics

from .channel import UNKNOWN_CHANNEL, channel_from_reference


def _capture_personless(event: str, properties: dict[str, Any]) -> None:
    ph_analytics.capture(
        event,
        distinct_id=str(uuid.uuid4()),
        properties={**properties, "$process_person_profile": False},
    )


def record_trial_issued(channel: str | None) -> None:
    """A trial licence was created for a new address."""
    _capture_personless("license_trial_issued", {"channel": channel or UNKNOWN_CHANNEL})


def record_license_purchased(checkout_session: Any, *, plan: str) -> None:
    """A paid checkout became a new licence. Called once per purchase."""
    amount_total = getattr(checkout_session, "amount_total", None)
    currency = getattr(checkout_session, "currency", None)
    channel = channel_from_reference(
        getattr(checkout_session, "client_reference_id", None)
    )
    _capture_personless(
        "license_purchased",
        {
            "plan": plan,
            # Stripe's minor units: 6000 is $60.00.
            "amount_total": amount_total if isinstance(amount_total, int) else None,
            "currency": currency.lower() if isinstance(currency, str) else None,
            "channel": channel or UNKNOWN_CHANNEL,
        },
    )
