"""Money returned suspends the one license it paid for: traced invoice -> subscription -> license, or by checkout.

Before, a subscription's charge traced to nothing, since its checkout session
names no payment, and a one-time payment with no Stripe customer was skipped.
"""

from __future__ import annotations

import pytest

from license.tests.billing_harness import Billing, billing, post_event
from license.tests.stripe_fake import event, invoice

pytestmark = pytest.mark.unit


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Billing:
    return billing(monkeypatch)


def a_firm_and_another(env: Billing) -> None:
    """Two Business licenses, so a wrong trace shows as the wrong one suspended."""
    for license_id, subscription_id in (
        ("lic-firm", "sub_firm"),
        ("lic-other", "sub_other"),
    ):
        env.keygen.add(
            license_id,
            policy="policy-business",
            plan="business",
            email=f"{license_id}@example.com",
            stripeSubscriptionId=subscription_id,
        )


def charge(payment_intent: str, *, refunded: bool = True, customer=None) -> dict:
    return {
        "id": f"ch_{payment_intent}",
        "object": "charge",
        "amount": 6000,
        "amount_refunded": 6000 if refunded else 1500,
        "refunded": refunded,
        "customer": customer,
        "payment_intent": payment_intent,
    }


def status_of(env: Billing, license_id: str) -> str:
    return env.keygen.licenses[license_id]["attributes"]["status"]


def charged_for(
    env: Billing, payment_intent: str, subscription_id: str, reason: str
) -> None:
    invoice_id = f"in_{payment_intent}"
    env.stripe.invoices[invoice_id] = invoice(
        invoice_id, subscription_id, reason=reason
    )
    env.stripe.invoice_paid_by[payment_intent] = invoice_id


@pytest.mark.parametrize("reason", ["subscription_create", "subscription_cycle"])
async def test_a_refunded_year_suspends_the_license_its_subscription_pays_for(
    env: Billing, reason: str
) -> None:
    a_firm_and_another(env)
    charged_for(env, "pi_year", "sub_firm", reason)

    response = await post_event(event("charge.refunded", charge("pi_year")))

    assert response.status_code == 200
    assert status_of(env, "lic-firm") == "SUSPENDED"
    assert status_of(env, "lic-other") == "ACTIVE"


async def test_a_refunded_payment_for_added_people_suspends_nothing(
    env: Billing,
) -> None:
    """The proration is not the license's price; the year is still paid for."""
    a_firm_and_another(env)
    charged_for(env, "pi_people", "sub_firm", "subscription_update")

    await post_event(event("charge.refunded", charge("pi_people")))

    assert status_of(env, "lic-firm") == "ACTIVE"


async def test_a_partial_refund_of_a_year_suspends_nothing(env: Billing) -> None:
    a_firm_and_another(env)
    charged_for(env, "pi_year", "sub_firm", "subscription_cycle")

    await post_event(event("charge.refunded", charge("pi_year", refunded=False)))

    assert status_of(env, "lic-firm") == "ACTIVE"


async def test_a_dispute_suspends_the_license_the_payment_bought(env: Billing) -> None:
    a_firm_and_another(env)
    charged_for(env, "pi_year", "sub_firm", "subscription_cycle")
    dispute = {
        "id": "dp_1",
        "object": "dispute",
        "amount": 6000,
        "charge": "ch_pi_year",
        "payment_intent": "pi_year",
        "status": "needs_response",
    }

    response = await post_event(event("charge.dispute.created", dispute))

    assert response.status_code == 200
    assert status_of(env, "lic-firm") == "SUSPENDED"
    assert status_of(env, "lic-other") == "ACTIVE"


async def test_a_one_time_payment_with_no_stripe_customer_is_still_traced(
    env: Billing,
) -> None:
    """A Payment Link's default customer_creation makes no customer for a one-time price."""
    env.keygen.add(
        "lic-once",
        policy="policy-individual",
        plan="individual",
        email="once@example.com",
        checkoutSessionId="cs_once",
    )
    env.stripe.sessions["cs_once"] = {
        "id": "cs_once",
        "object": "checkout.session",
        "mode": "payment",
        "payment_intent": "pi_once",
    }

    await post_event(event("charge.refunded", charge("pi_once", customer=None)))

    assert status_of(env, "lic-once") == "SUSPENDED"


async def test_a_refund_of_an_individual_subscription_sold_before_the_change(
    env: Billing,
) -> None:
    """No stripeSubscriptionId on it: the subscription's checkout session names it."""
    env.keygen.add(
        "lic-solo",
        policy="policy-individual",
        plan="individual",
        email="solo@example.com",
        checkoutSessionId="cs_solo",
    )
    env.stripe.sessions["cs_solo"] = {
        "id": "cs_solo",
        "object": "checkout.session",
        "mode": "subscription",
        "subscription": "sub_solo",
    }
    charged_for(env, "pi_solo", "sub_solo", "subscription_create")

    await post_event(event("charge.refunded", charge("pi_solo", customer="cus_solo")))

    assert status_of(env, "lic-solo") == "SUSPENDED"


async def test_a_refund_that_traces_to_no_license_suspends_nothing(
    env: Billing,
) -> None:
    a_firm_and_another(env)

    response = await post_event(event("charge.refunded", charge("pi_unknown")))

    assert response.status_code == 200
    assert {status_of(env, lid) for lid in env.keygen.licenses} == {"ACTIVE"}
