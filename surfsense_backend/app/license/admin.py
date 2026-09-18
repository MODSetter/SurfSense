"""Changing a license after the fact: refunds and corrected addresses."""

from __future__ import annotations

import logging
from typing import cast

from app.license import keygen
from app.license.email.address import fold_email, normalize_email
from app.license.keygen import LicensePlan
from app.license.models import (
    META_CUSTOMER,
    META_EMAIL,
    META_PLAN,
    META_TRIAL_KEY,
    IssuedLicense,
    LicenseRecord,
)

logger = logging.getLogger(__name__)


async def suspend_licenses_for_customer(
    customer_id: str,
    *,
    keygen_license_id: str | None = None,
) -> int:
    """Suspend everything a refunded customer holds. Returns how many."""
    if keygen_license_id:
        await keygen.suspend_license(keygen_license_id)
        return 1

    matches = await keygen.list_licenses(metadata={META_CUSTOMER: customer_id})
    for record in matches:
        license_id = str(record.get("id") or "")
        if license_id:
            await keygen.suspend_license(license_id)
    return len(matches)


async def correct_license_email(
    record: LicenseRecord,
    new_email: str,
) -> IssuedLicense:
    """Point a license at the address its buyer actually owns.

    Rewrites the stored address so the customer can use ``/license/resend``
    themselves from now on. Sending them the file without this leaves the typo
    in place and makes every future re-download a support ticket.
    """
    corrected = normalize_email(new_email)
    if not corrected:
        raise ValueError("A replacement email is required")

    metadata = dict(record.metadata)
    metadata[META_EMAIL] = corrected
    if metadata.get(META_PLAN) == "trial":
        # The dedupe index folds +tags; leaving the old key would let the
        # corrected address claim a second trial.
        metadata[META_TRIAL_KEY] = fold_email(corrected)

    await keygen.update_license_metadata(record.keygen_license_id, metadata)
    certificate = await keygen.checkout_license(record.keygen_license_id)
    logger.info(
        "Corrected license %s email %r -> %r",
        record.keygen_license_id,
        record.metadata.get(META_EMAIL),
        corrected,
    )
    return IssuedLicense(
        keygen_license_id=record.keygen_license_id,
        certificate=certificate,
        plan=cast(LicensePlan, metadata.get(META_PLAN) or "individual"),
        email=corrected,
        max_users=record.max_users,
    )
