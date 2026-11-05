"""Reading licenses back out of Keygen.

Keygen is the system of record, so "find" here means "filter its metadata".
"""

from __future__ import annotations

from typing import Any, cast

from license import keygen
from license.email.address import fold_email, normalize_email
from license.fresh_file import fresh_file
from license.jobs import jobs_of
from license.keygen import LicensePlan
from license.models import (
    META_EMAIL,
    META_FIRM,
    META_PLAN,
    META_SESSION,
    META_TRIAL_KEY,
    IssuedLicense,
    LicenseNotFoundError,
    LicenseRecord,
)

_SUSPENDED_STATUSES = {"SUSPENDED", "BANNED"}


def is_suspended(record: dict[str, Any]) -> bool:
    status = (record.get("attributes") or {}).get("status")
    return str(status or "").upper() in _SUSPENDED_STATUSES


async def issued_from_keygen(license_record: dict[str, Any]) -> IssuedLicense | None:
    """The license checked out ready to deliver, or ``None`` when Keygen refuses it a file."""
    attributes = license_record.get("attributes") or {}
    metadata = attributes.get("metadata") or {}
    license_id = str(license_record.get("id") or "")
    certificate = await fresh_file(license_id)
    if certificate is None:
        return None
    return IssuedLicense(
        keygen_license_id=license_id,
        certificate=certificate,
        plan=cast(LicensePlan, metadata.get(META_PLAN) or "individual"),
        email=str(metadata.get(META_EMAIL) or ""),
        max_users=attributes.get("maxUsers"),
        firm=str(metadata.get(META_FIRM) or "") or None,
        jobs=jobs_of(metadata),
    )


async def issued_for_id(license_id: str) -> IssuedLicense | None:
    """The license with this id, checked out ready to deliver."""
    record = await keygen.get_license(license_id)
    if record is None:
        return None
    return await issued_from_keygen(record)


async def existing_for_session(session_id: str) -> IssuedLicense | None:
    """The license already issued for this checkout session, if any.

    This Keygen list is the idempotency check: with no table, there is no
    unique constraint to lean on.
    """
    matches = await keygen.list_licenses(metadata={META_SESSION: session_id}, limit=1)
    if not matches:
        return None
    return await issued_from_keygen(matches[0])


async def licenses_for_email(email: str) -> list[IssuedLicense]:
    """Every usable license registered to an address, checked out. The whole of "resend".

    Suspended licenses are skipped. A refund suspends the license, and mailing
    someone a file for a purchase they were refunded is confusing rather than
    dangerous -- the scraper API rejects the key server-side either way
    (contract 2). Skipping keeps the two consistent.
    """
    matches = await keygen.list_licenses(metadata={META_EMAIL: normalize_email(email)})
    licenses: list[IssuedLicense] = []
    for record in matches:
        if not record.get("id") or is_suspended(record):
            continue
        issued = await issued_from_keygen(record)
        if issued is not None:
            licenses.append(issued)
    return licenses


async def find_license_by_checkout_session(session_id: str) -> LicenseRecord:
    """Resolve the license a Stripe checkout produced.

    Support matches on the *payment*, not on how similar two addresses look:
    the buyer proves the charge in Stripe, Stripe gives the session id, and the
    session id names exactly one license. No judgement call about whether
    "gmial" meant "gmail".
    """
    matches = await keygen.list_licenses(metadata={META_SESSION: session_id}, limit=2)
    if not matches:
        raise LicenseNotFoundError(
            f"No license carries checkoutSessionId {session_id!r}"
        )
    if len(matches) > 1:
        # Two licenses for one payment means the idempotency race lost. Refuse
        # rather than guess which one the customer should keep.
        raise LicenseNotFoundError(
            f"{len(matches)} licenses carry checkoutSessionId {session_id!r}; "
            "resolve the duplicate in Keygen before correcting it"
        )
    return license_record(matches[0])


async def find_trial_license_by_email(email: str) -> LicenseRecord:
    """Resolve the trial issued to exactly this address, for a support correction.

    A trial has no payment to prove, so the anchor is the address as it was
    typed: support acts only on the exact address the requester says they
    entered, never on one that merely looks like it. Filtering on the trial key
    as well keeps a paid licence at that address out of reach.
    """
    typed = normalize_email(email)
    matches = await keygen.list_licenses(
        metadata={META_EMAIL: typed, META_TRIAL_KEY: fold_email(typed)}, limit=2
    )
    if not matches:
        raise LicenseNotFoundError(f"No trial license was issued to {typed!r}")
    if len(matches) > 1:
        raise LicenseNotFoundError(
            f"{len(matches)} trial licenses were issued to {typed!r}; "
            "resolve the duplicate in Keygen before correcting it"
        )
    return license_record(matches[0])


def license_record(record: dict[str, Any]) -> LicenseRecord:
    attributes = record.get("attributes") or {}
    return LicenseRecord(
        keygen_license_id=str(record.get("id") or ""),
        metadata=dict(attributes.get("metadata") or {}),
        max_users=attributes.get("maxUsers"),
        expiry=attributes.get("expiry"),
    )
