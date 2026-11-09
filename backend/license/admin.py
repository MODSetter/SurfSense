"""Changing a license after the fact: corrected addresses."""

from __future__ import annotations

import logging
from typing import cast

from license import keygen
from license.email.address import fold_email, normalize_email
from license.fresh_file import fresh_file
from license.jobs import jobs_of
from license.keygen import LicensePlan
from license.models import (
    META_EMAIL,
    META_FIRM,
    META_PLAN,
    META_TRIAL_KEY,
    IssuedLicense,
    LicenseRecord,
)

logger = logging.getLogger(__name__)


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
    logger.info(
        "Corrected license %s email %r -> %r",
        record.keygen_license_id,
        record.metadata.get(META_EMAIL),
        corrected,
    )
    certificate = await fresh_file(record.keygen_license_id)
    if certificate is None:
        # The address is corrected either way; a suspended license gets no file.
        raise ValueError(
            f"License {record.keygen_license_id} is not in good standing; "
            "its address was corrected but no file was checked out"
        )
    return IssuedLicense(
        keygen_license_id=record.keygen_license_id,
        certificate=certificate,
        plan=cast(LicensePlan, metadata.get(META_PLAN) or "individual"),
        email=corrected,
        max_users=record.max_users,
        firm=str(metadata.get(META_FIRM) or "") or None,
        jobs=jobs_of(metadata),
    )
