"""The one license a Stripe subscription pays for."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import Any

import anyio

from license import keygen
from license.models import META_SUBSCRIPTION, LicenseNotFoundError, LicenseRecord
from license.records import find_license_by_checkout_session, license_record

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SubscribedLicense:
    record: LicenseRecord
    # False for a license sold before stripeSubscriptionId was written, found
    # through its checkout session; the caller writes the id on.
    recorded: bool


async def license_for_subscription(
    subscription_id: str,
    stripe_client: Any,
    *,
    through_checkout: bool = True,
) -> SubscribedLicense | None:
    """By ``stripeSubscriptionId``, else through the checkout session that started it.

    Two licenses on one subscription is a support case, never a guess: acting
    on the wrong one would renew, recount or suspend a firm that did not pay.
    """
    matches = await keygen.list_licenses(
        metadata={META_SUBSCRIPTION: subscription_id}, limit=2
    )
    if len(matches) > 1:
        logger.warning(
            "%d licenses carry stripeSubscriptionId %s; acting on neither",
            len(matches),
            subscription_id,
        )
        return None
    if matches:
        return SubscribedLicense(license_record(matches[0]), recorded=True)
    if not through_checkout or stripe_client is None:
        return None

    # In a thread: the event loop also streams every plugin call.
    sessions = await anyio.to_thread.run_sync(
        partial(
            stripe_client.v1.checkout.sessions.list,
            params={"subscription": subscription_id, "limit": 1},
        )
    )
    if not sessions.data:
        return None
    try:
        record = await find_license_by_checkout_session(sessions.data[0].id)
    except LicenseNotFoundError:
        return None
    return SubscribedLicense(record, recorded=False)


def with_subscription(record: LicenseRecord, subscription_id: str) -> dict[str, str]:
    """The license's metadata with the subscription written on; Keygen replaces it whole."""
    return {**record.metadata, META_SUBSCRIPTION: subscription_id}
