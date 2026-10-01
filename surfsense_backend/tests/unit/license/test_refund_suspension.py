"""A refund suspends the licence that charge paid for, and only when fully refunded.

The webhook used to suspend every licence the Stripe customer held, so a partial
refund, or a refund of one of two purchases, silently disabled a licence the
customer still paid for.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.license.purchase  # noqa: F401  registers the refund handler
from app.license import keygen
from app.license.models import META_CUSTOMER, META_SESSION
from app.payments import registry

pytestmark = pytest.mark.unit

HELD = {"cs_first": "lic-first", "cs_second": "lic-second"}


def charge(amount_refunded: int, *, amount: int = 4900) -> SimpleNamespace:
    """A charge.refunded object for the second of the customer's two purchases."""
    return SimpleNamespace(
        customer="cus_1",
        amount=amount,
        amount_refunded=amount_refunded,
        refunded=amount_refunded >= amount,
        payment_intent="pi_second",
    )


def stripe_client(sessions: dict[str, str]) -> SimpleNamespace:
    """Stripe's checkout session list, keyed by payment intent."""

    def list_sessions(params: dict) -> SimpleNamespace:
        found = sessions.get(params["payment_intent"])
        return SimpleNamespace(data=[SimpleNamespace(id=found)] if found else [])

    sessions_api = SimpleNamespace(list=list_sessions)
    return SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessions_api))
    )


@pytest.fixture
def suspended(monkeypatch) -> list[str]:
    """A customer holding two licences in Keygen; records what gets suspended."""
    calls: list[str] = []

    async def list_licenses(*, metadata=None, limit=100, **_):
        metadata = metadata or {}
        if META_SESSION in metadata:
            license_id = HELD.get(metadata[META_SESSION])
            return (
                [{"id": license_id, "attributes": {"metadata": {}}}]
                if license_id
                else []
            )
        if metadata.get(META_CUSTOMER) == "cus_1":
            return [
                {"id": lid, "attributes": {"metadata": {}}} for lid in HELD.values()
            ]
        return []

    async def suspend_license(license_id: str) -> None:
        calls.append(license_id)

    monkeypatch.setattr(keygen, "list_licenses", list_licenses)
    monkeypatch.setattr(keygen, "suspend_license", suspend_license)
    return calls


async def refund(obj: SimpleNamespace, sessions: dict[str, str]) -> None:
    handler = registry.event_handler("charge.refunded")
    await handler(obj, db_session=None, stripe_client=stripe_client(sessions))


async def test_a_partial_refund_suspends_nothing(suspended) -> None:
    """A goodwill refund leaves the customer a licence they still paid for."""
    await refund(charge(amount_refunded=1000), {"pi_second": "cs_second"})

    assert suspended == []


async def test_a_full_refund_suspends_only_the_licence_that_charge_bought(
    suspended,
) -> None:
    """The customer's other purchase keeps working."""
    await refund(charge(amount_refunded=4900), {"pi_second": "cs_second"})

    assert suspended == ["lic-second"]


async def test_a_refund_no_licence_can_be_traced_to_suspends_nothing(
    suspended,
) -> None:
    """Guessing would disable a licence silently; support gets a log line instead."""
    await refund(charge(amount_refunded=4900), {})

    assert suspended == []
