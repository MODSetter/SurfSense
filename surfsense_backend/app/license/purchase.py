"""What a Stripe event means for a license.

Registers with the payments webhook rather than being called from it, so
payments stays ignorant of licensing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import config
from app.payments import registry
from app.payments.schemas import StripeWebhookResponse

from .admin import suspend_licenses_for_customer
from .checkout import resolve_license_plan
from .email.deliver import deliver_licenses
from .issue import fulfill_license_session
from .models import LicenseIssueError, LicenseNotFoundError
from .records import find_license_by_checkout_session

logger = logging.getLogger(__name__)


def _claims_checkout(
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
    if not (config.STRIPE_PRICE_LICENSE_INDIVIDUAL or config.STRIPE_PRICE_LICENSE_TEAM):
        return False
    try:
        return (
            resolve_license_plan(checkout_session, stripe_client=stripe_client)
            is not None
        )
    except LicenseIssueError:
        return False


async def _fulfill(
    checkout_session: Any, *, stripe_client: Any, **_: Any
) -> StripeWebhookResponse:
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
            idempotency_key=str(getattr(checkout_session, "id", "")) or None,
        )
    except Exception:
        logger.warning(
            "Issued license %s but could not email it to %s",
            issued.keygen_license_id,
            issued.email,
            exc_info=True,
        )
    return StripeWebhookResponse()


async def _suspend_refunded(
    charge: Any, *, stripe_client: Any = None, **_: Any
) -> StripeWebhookResponse:
    """Suspend the licence a fully refunded charge paid for, and no other.

    Suspend rather than revoke: reversible, still listable for support, and
    ``validate-key`` then reports SUSPENDED, which contract 2 maps to the
    ``revoked`` reason. A partial refund suspends nothing: it is a goodwill or
    seat adjustment, and the rest of the purchase is still paid for.
    """
    customer = getattr(charge, "customer", None)
    customer_id = (
        customer if isinstance(customer, str) else getattr(customer, "id", None)
    )
    if not customer_id or not _fully_refunded(charge):
        return StripeWebhookResponse()

    try:
        license_id = await _license_paid_by(charge, stripe_client)
        if license_id is None:
            # A wrong suspension is silent (resend skips suspended licences), so
            # a refund that cannot be traced to one licence is left to support.
            logger.warning(
                "Refund for customer %s traces to no single license; not suspending",
                customer_id,
            )
            return StripeWebhookResponse()
        await suspend_licenses_for_customer(
            str(customer_id), keygen_license_id=license_id
        )
    except Exception:
        # Swallowed on purpose: a 500 makes Stripe retry, and a retry would
        # re-run the suspension.
        logger.exception(
            "Could not suspend licenses for refunded customer %s", customer_id
        )
        return StripeWebhookResponse()

    logger.info(
        "Suspended license %s after refund for customer %s", license_id, customer_id
    )
    return StripeWebhookResponse()


def _fully_refunded(charge: Any) -> bool:
    if getattr(charge, "refunded", False):
        return True
    amount = getattr(charge, "amount", None)
    refunded = getattr(charge, "amount_refunded", None)
    return isinstance(amount, int) and isinstance(refunded, int) and refunded >= amount


async def _license_paid_by(charge: Any, stripe_client: Any) -> str | None:
    """The one licence the charge's checkout session issued, through Stripe."""
    payment_intent = getattr(charge, "payment_intent", None)
    payment_intent_id = (
        payment_intent
        if isinstance(payment_intent, str)
        else getattr(payment_intent, "id", None)
    )
    if not payment_intent_id or stripe_client is None:
        return None
    sessions = stripe_client.v1.checkout.sessions.list(
        params={"payment_intent": payment_intent_id, "limit": 1}
    )
    if not sessions.data:
        return None
    try:
        record = await find_license_by_checkout_session(sessions.data[0].id)
    except LicenseNotFoundError:
        return None
    return record.keygen_license_id or None


registry.claims_checkout("license", _claims_checkout, _fulfill)
registry.on_event("charge.refunded", _suspend_refunded)
