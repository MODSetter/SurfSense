"""Live Keygen contract; opt in with KEYGEN_INTEGRATION=1.

Every other license test fakes the client, so the HTTP shapes and above all the
metadata filter spellings are otherwise never checked against Keygen itself. A
misspelled filter returns an empty list rather than an error, which reads as
"no license": the duplicate it lets through, or the refund it never suspends,
is the failure this test exists to catch.

Run it against a Keygen CE account (images in ``docker/keygen/``) with the
usual ``KEYGEN_ACCOUNT_ID``, ``KEYGEN_API_TOKEN`` and ``KEYGEN_POLICY_INDIVIDUAL``
set, plus ``KEYGEN_API_URL``/``KEYGEN_HOST`` for a self-hosted one:

    KEYGEN_INTEGRATION=1 pytest tests/integration/license

Each run creates one license under a random id and suspends it afterwards;
Keygen's client has no delete, and a suspended record is what a refund leaves.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.license import keygen
from app.license.models import META_CUSTOMER, META_EMAIL, META_SESSION

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
    metadata = {META_SESSION: f"cs_contract_{marker}", META_CUSTOMER: f"cus_{marker}"}
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

    assert ids(by_session) == [license_id]
    assert ids(by_customer) == [license_id]
    assert ids(by_email) == [license_id]


async def test_a_misspelled_key_finds_nothing_rather_than_failing(
    license_on_keygen,
) -> None:
    """Why the spellings live in one place: Keygen answers a wrong key with []."""
    _, _, metadata = license_on_keygen

    snake_case = await keygen.list_licenses(
        metadata={"checkout_session_id": metadata[META_SESSION]}
    )

    assert snake_case == []
