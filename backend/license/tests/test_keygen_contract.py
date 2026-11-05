"""Live Keygen contract; opt in with KEYGEN_INTEGRATION=1.

Every other license test fakes the client, so the HTTP shapes and the metadata
filter keys are otherwise never checked against Keygen itself. Keygen
underscores every filter key before it compares, so ``checkoutSessionId`` and
``checkout_session_id`` are one key; what can go wrong is a different word,
which answers an empty list rather than an error and reads as "no license":
the duplicate it lets through, or the refund it never suspends, is the failure
this test exists to catch.

Run it against a Keygen CE account (images in ``docker/keygen/``) with the
usual ``KEYGEN_ACCOUNT_ID``, ``KEYGEN_API_TOKEN`` and ``KEYGEN_POLICY_INDIVIDUAL``
set, plus ``KEYGEN_API_URL``/``KEYGEN_HOST`` for a self-hosted one, from ``backend/``:

    KEYGEN_INTEGRATION=1 uv run pytest license/tests/test_keygen_contract.py

Each test creates its own license and suspends it afterwards; Keygen's client
has no delete, and a suspended record is what a refund leaves.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from license import keygen
from license.job_packs.verdict import LicenseVerdict, license_verdict
from license.jobs import JOBS, jobs_metadata
from license.models import (
    META_CUSTOMER,
    META_EMAIL,
    META_JOBS,
    META_SESSION,
    META_SUBSCRIPTION,
)

pytestmark = pytest.mark.integration

if os.getenv("KEYGEN_INTEGRATION") != "1":
    pytest.skip(
        "Live Keygen contract; set KEYGEN_INTEGRATION=1 with Keygen credentials",
        allow_module_level=True,
    )


@pytest.fixture
async def license_on_keygen():
    """One license carrying the metadata a purchase writes, suspended afterwards."""
    marker = uuid4().hex
    email = f"contract-{marker[:12]}@example.com"
    metadata = {
        META_SESSION: f"cs_contract_{marker}",
        META_CUSTOMER: f"cus_{marker}",
        META_SUBSCRIPTION: f"sub_{marker}",
    }
    license_id = await keygen.create_license(
        "individual", email, extra_metadata=metadata
    )
    yield license_id, email, metadata
    await keygen.suspend_license(license_id)


async def test_the_metadata_keys_the_app_writes_are_the_ones_it_can_filter_on(
    license_on_keygen,
) -> None:
    """Every lookup the portal, refunds and support make, against the real filter."""
    license_id, email, metadata = license_on_keygen

    def ids(records: list[dict]) -> list[str]:
        return [str(record.get("id")) for record in records]

    by_session = await keygen.list_licenses(
        metadata={META_SESSION: metadata[META_SESSION]}
    )
    by_customer = await keygen.list_licenses(
        metadata={META_CUSTOMER: metadata[META_CUSTOMER]}
    )
    by_email = await keygen.list_licenses(metadata={META_EMAIL: email})
    by_subscription = await keygen.list_licenses(
        metadata={META_SUBSCRIPTION: metadata[META_SUBSCRIPTION]}
    )

    assert ids(by_session) == [license_id]
    assert ids(by_customer) == [license_id]
    assert ids(by_email) == [license_id]
    assert ids(by_subscription) == [license_id]


async def test_a_key_with_another_word_finds_nothing_rather_than_failing(
    license_on_keygen,
) -> None:
    """Why the spellings live in models.py: a wrong word answers [], not an error."""
    license_id, _, metadata = license_on_keygen

    other_word = await keygen.list_licenses(
        metadata={"sessionId": metadata[META_SESSION]}
    )
    right_word = await keygen.list_licenses(
        metadata={META_SESSION: metadata[META_SESSION]}
    )

    assert other_word == []
    assert [str(record.get("id")) for record in right_word] == [license_id]


async def test_a_suspended_license_validates_as_such_but_still_checks_out() -> None:
    """Why every delivery validates first: a token's check-out checks no status."""
    license_id = await keygen.create_license(
        "individual", f"contract-{uuid4().hex[:12]}@example.com"
    )

    try:
        before = await keygen.validate_license(license_id)
    finally:
        await keygen.suspend_license(license_id)
    after = await keygen.validate_license(license_id)
    certificate = await keygen.checkout_license(license_id)

    assert before.code == "VALID"
    assert after.code == "SUSPENDED"
    assert certificate.startswith("-----BEGIN LICENSE FILE-----")


async def test_a_renewal_moves_the_expiry_on_the_same_key(license_on_keygen) -> None:
    license_id, _, _ = license_on_keygen
    record = await keygen.get_license(license_id)
    assert record is not None
    key = record["attributes"]["key"]
    renewed_to = (datetime.now(UTC) + timedelta(days=400)).replace(microsecond=0)

    await keygen.update_license(license_id, expiry=renewed_to)
    by_key = await keygen.validate_key(key)

    assert by_key.code == "VALID"
    assert by_key.record is not None
    assert by_key.record["id"] == license_id
    assert datetime.fromisoformat(by_key.record["attributes"]["expiry"]) == renewed_to


async def test_validate_key_answers_the_license_jobs() -> None:
    """The job pack route reads the jobs from validate-key, as the app reads them from its file."""
    license_id = await keygen.create_license(
        "individual",
        f"contract-{uuid4().hex[:12]}@example.com",
        extra_metadata={META_JOBS: jobs_metadata()},
    )
    try:
        record = await keygen.get_license(license_id)
        assert record is not None
        verdict = await license_verdict(record["attributes"]["key"])
    finally:
        await keygen.suspend_license(license_id)

    assert verdict == LicenseVerdict("VALID", tuple(JOBS))
