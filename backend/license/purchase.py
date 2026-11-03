"""What a Stripe event means for a license: a purchase to fulfil, or money returned to suspend it for."""

from __future__ import annotations

import logging
from typing import Any

from license import keygen

from .charged_license import license_paid_by
from .checkout import license_prices_configured, resolve_license_plan
from .email.deliver import deliver_licenses
from .email.message import BusinessCopy
from .issue import fulfill_license_session
from .models import LicenseIssueError

logger = logging.getLogger(__name__)


async def claims_checkout(
    metadata: dict[str, str], checkout_session: Any, stripe_client: Any
) -> bool:
    """Whether this paid session bought a desktop license.

    API-created sessions say so in metadata. Payment Links carry none, so the
    price ID is the fallback -- which is only consulted when a license price is
    actually configured, so ordinary checkouts cost no extra Stripe call.
    """
    purchase_type = metadata.get("purchase_type")
    if purchase_type == "license":
        return True
    # Any other explicit type is someone else's. Saying so here is what keeps
    # the line-item lookup below off the path of every credit checkout.
    if purchase_type:
        return False
    if not license_prices_configured():
        return False
    try:
        return (
            await resolve_license_plan(checkout_session, stripe_client=stripe_client)
            is not None
        )
    except LicenseIssueError:
        return False


async def fulfill(checkout_session: Any, *, stripe_client: Any) -> None:
    """Issue the license and email it.

    Delivery failure does not fail the webhook: the license exists, the success
    page serves it regardless, and a Stripe retry would only risk a duplicate.
    """
    issued = await fulfill_license_session(
        checkout_session, stripe_client=stripe_client
    )
    try:
        await deliver_licenses(
            "purchase",
            to=issued.email,
            certificates=[issued.certificate],
            business=BusinessCopy.of(issued),
            idempotency_key=str(getattr(checkout_session, "id", "")) or None,
        )
    except Exception:
        logger.warning(
            "Issued license %s but could not email it to %s",
            issued.keygen_license_id,
            issued.email,
            exc_info=True,
        )


async def suspend_refunded(charge: Any, *, stripe_client: Any = None) -> None:
    """Suspend the licence a fully refunded charge paid for, and no other.

    Suspend rather than revoke: reversible, still listable for support, and
    ``validate-key`` then reports SUSPENDED, which contract 2 maps to the
    ``revoked`` reason. A partial refund suspends nothing: it is a goodwill or
    seat adjustment, and the rest of the purchase is still paid for.
    """
    if not _fully_refunded(charge):
        return
    await _suspend_paid_by(
        getattr(charge, "payment_intent", None), stripe_client, why="refund"
    )


async def suspend_disputed(dispute: Any, *, stripe_client: Any = None) -> None:
    """Suspend the licence a disputed payment paid for, as a full refund does.

    A dispute won later is reinstated by support, since a dispute can close
    in the buyer's favour after any number of updates.
    """
    await _suspend_paid_by(
        getattr(dispute, "payment_intent", None), stripe_client, why="dispute"
    )


async def _suspend_paid_by(
    payment_intent: Any, stripe_client: Any, *, why: str
) -> None:
    try:
        license_id = await license_paid_by(payment_intent, stripe_client)
        if license_id is None:
            # A wrong suspension is silent (resend skips suspended licences), so
            # money returned that cannot be traced to one licence is left to support.
            logger.warning(
                "A %s traces to no single license; not suspending (payment %s)",
                why,
                payment_intent if isinstance(payment_intent, str) else "?",
            )
            return
        await keygen.suspend_license(license_id)
    except Exception:
        # Swallowed on purpose: a 500 makes Stripe retry, and a retry would
        # re-run the suspension.
        logger.exception("Could not suspend the license after a %s", why)
        return

    logger.info("Suspended license %s after a %s", license_id, why)


def _fully_refunded(charge: Any) -> bool:
    if getattr(charge, "refunded", False):
        return True
    amount = getattr(charge, "amount", None)
    refunded = getattr(charge, "amount_refunded", None)
    return isinstance(amount, int) and isinstance(refunded, int) and refunded >= amount
