"""Reading the three sources a cohort joins: Keygen, Stripe and the plugin host."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx2
import pytest

from license.cohorts.keygen_licences import read_licences
from license.cohorts.models import Purchase
from license.cohorts.plugin_host_first_seen import read_first_seen
from license.cohorts.stripe_purchases import add_stripe_view

pytestmark = pytest.mark.unit


def licence(license_id, created, metadata, status="ACTIVE"):
    return {
        "id": license_id,
        "attributes": {"created": created, "metadata": metadata, "status": status},
    }


def keygen_listing(*records):
    async def iterate():
        for record in records:
            yield record

    return iterate


async def test_trials_and_purchases_are_told_apart_by_plan():
    trials, purchases = await read_licences(
        keygen_listing(
            licence(
                "lic-t",
                "2026-10-14T09:30:00.000Z",
                {
                    "plan": "trial",
                    "email": "Ana+x@acme.test",
                    "trialKey": "ana@acme.test",
                },
            ),
            licence(
                "lic-p",
                "2026-10-20T12:00:00.000Z",
                {
                    "plan": "individual",
                    "email": "ana+buy@acme.test",
                    "checkoutSessionId": "cs_1",
                },
                status="SUSPENDED",
            ),
            licence("lic-x", None, {"plan": "trial", "email": "b@acme.test"}),
        )
    )

    [trial] = trials
    assert (trial.licence_id, trial.created, trial.folded_email) == (
        "lic-t",
        date(2026, 10, 14),
        "ana@acme.test",
    )
    [purchase] = purchases
    assert purchase.paid_on == date(2026, 10, 20)
    assert purchase.folded_emails == {"ana@acme.test"}
    assert purchase.checkout_session_id == "cs_1"
    # A full refund suspends the licence, so Keygen alone knows of it.
    assert purchase.refunded is True


async def test_a_trial_without_a_trial_key_is_folded_from_its_address():
    trials, _ = await read_licences(
        keygen_listing(
            licence(
                "lic-t",
                "2026-10-14T09:30:00Z",
                {"plan": "trial", "email": "Ana+x@Acme.test"},
            )
        )
    )

    assert trials[0].folded_email == "ana@acme.test"


class FakeStripe:
    """Stripe's session retrieve, answering from a table of sessions."""

    def __init__(self, sessions):
        self.sessions = sessions
        self.asked = []
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=self.retrieve))
        )

    def retrieve(self, session_id, params=None):
        self.asked.append((session_id, params))
        if session_id not in self.sessions:
            raise RuntimeError("No such checkout session")
        return self.sessions[session_id]


def session(*, typed, customer=None, charge=None):
    return SimpleNamespace(
        customer_details=SimpleNamespace(email=typed),
        customer=customer,
        payment_intent=SimpleNamespace(latest_charge=charge),
    )


def test_stripe_adds_the_checkout_and_customer_addresses_and_full_refunds():
    purchase = Purchase(
        date(2026, 10, 20), {"ana@acme.test"}, checkout_session_id="cs_1"
    )
    stripe = FakeStripe(
        {
            "cs_1": session(
                typed="Ana+Pay@Acme.test",
                customer=SimpleNamespace(email="billing@acme.test"),
                charge=SimpleNamespace(
                    refunded=False, amount=6000, amount_refunded=6000
                ),
            )
        }
    )

    failed = add_stripe_view([purchase], stripe)

    assert failed == 0
    assert purchase.folded_emails == {"ana@acme.test", "billing@acme.test"}
    assert purchase.refunded is True
    assert stripe.asked[0][1] == {
        "expand": ["customer", "payment_intent.latest_charge"]
    }


def test_a_partial_refund_is_not_a_refund():
    purchase = Purchase(date(2026, 10, 20), set(), checkout_session_id="cs_1")
    stripe = FakeStripe(
        {
            "cs_1": session(
                typed="ana@acme.test",
                customer="cus_unexpanded",
                charge=SimpleNamespace(
                    refunded=False, amount=6000, amount_refunded=1000
                ),
            )
        }
    )

    add_stripe_view([purchase], stripe)

    assert purchase.folded_emails == {"ana@acme.test"}
    assert purchase.refunded is False


def test_a_failed_lookup_is_counted_and_a_purchase_without_a_session_is_skipped():
    missing = Purchase(date(2026, 10, 20), set(), checkout_session_id="cs_gone")
    invoiced = Purchase(date(2026, 10, 20), {"ops@acme.test"})
    stripe = FakeStripe({})

    assert add_stripe_view([missing, invoiced], stripe) == 1
    assert [asked for asked, _ in stripe.asked] == ["cs_gone"]


async def test_first_seen_days_are_read_with_the_admin_token():
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, json={"licences": {"lic-1": "2026-10-15", "lic-2": "not a date"}}
        )

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        first_seen = await read_first_seen("https://host.test/", "tok", client=client)

    assert first_seen == {"lic-1": date(2026, 10, 15)}
    assert str(seen[0].url) == "https://host.test/admin/usage/first-seen"
    assert seen[0].headers["Authorization"] == "Bearer tok"
