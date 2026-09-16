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
from .models import LicenseIssueError

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


async def _suspend_refunded(charge: Any, **_: Any) -> StripeWebhookResponse:
    """Suspend a refunded buyer's licenses.

    Suspend rather than revoke: reversible, still listable for support, and
    ``validate-key`` then reports SUSPENDED, which contract 2 maps to the
    ``revoked`` reason.
    """
    customer = getattr(charge, "customer", None)
    customer_id = (
        customer if isinstance(customer, str) else getattr(customer, "id", None)
    )
    if not customer_id:
        return StripeWebhookResponse()

    try:
        suspended = await suspend_licenses_for_customer(str(customer_id))
    except Exception:
        logger.exception(
            "Could not suspend licenses for refunded customer %s", customer_id
        )
        return StripeWebhookResponse()

    if suspended:
        logger.info(
            "Suspended %d license(s) after refund for customer %s",
            suspended,
            customer_id,
        )
    return StripeWebhookResponse()


registry.claims_checkout("license", _claims_checkout, _fulfill)
registry.on_event("charge.refunded", _suspend_refunded)
