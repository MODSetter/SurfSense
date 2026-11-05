"""A subscription's year: a paid renewal extends the same key, seats move its count, an end lets it lapse."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from license.tests.billing_harness import (
    BUSINESS_PRICE,
    INDIVIDUAL_PRICE,
    Billing,
    billing,
    post_event,
)
from license.tests.stripe_fake import event, invoice, subscription

pytestmark = pytest.mark.unit

YEAR_ONE_END = datetime(2027, 11, 3, tzinfo=UTC)
YEAR_TWO_END = datetime(2028, 11, 3, tzinfo=UTC)
GRACE = timedelta(days=30)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Billing:
    return billing(monkeypatch)


def firm_license(env: Billing, *, status: str = "ACTIVE", people: int = 3) -> None:
    """A Business license sold on subscription sub_firm, in its first year."""
    env.keygen.add(
        "lic-firm",
        status,
        policy="policy-business",
        expiry=(YEAR_ONE_END + GRACE).isoformat(),
        max_users=people,
        plan="business",
        email="partner@acme.example",
        firm="Acme Accounting LLP",
        jobs="JOB_QUESTIONNAIRE",
        stripeSubscriptionId="sub_firm",
        checkoutSessionId="cs_firm",
    )


def renewed(env: Billing, subscription_id: str, *, people: int = 3, price: str) -> None:
    """Stripe has moved the subscription into its second year."""
    env.stripe.subscriptions[subscription_id] = subscription(
        subscription_id,
        period_end=int(YEAR_TWO_END.timestamp()),
        quantity=people,
        price=price,
    )


def paid(invoice_id: str, subscription_id: str, reason: str) -> bytes:
    return event("invoice.paid", invoice(invoice_id, subscription_id, reason=reason))


def expiry_of(env: Billing, license_id: str) -> datetime:
    return datetime.fromisoformat(
        env.keygen.licenses[license_id]["attributes"]["expiry"]
    )


# invoice.paid -----------------------------------------------------------------


async def test_a_paid_renewal_extends_the_same_license_to_the_new_year_plus_grace(
    env: Billing,
) -> None:
    firm_license(env)
    renewed(env, "sub_firm", price=BUSINESS_PRICE)

    response = await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))

    assert response.status_code == 200
    assert list(env.keygen.licenses) == ["lic-firm"]
    assert expiry_of(env, "lic-firm") == YEAR_TWO_END + GRACE


async def test_a_renewal_mails_the_renewed_file_in_the_business_copy(
    env: Billing,
) -> None:
    """For the computer that stays offline; the app fetches it when online."""
    firm_license(env)
    renewed(env, "sub_firm", price=BUSINESS_PRICE)

    await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))

    (mail,) = env.mail
    assert mail.to == "partner@acme.example"
    assert mail.subject == "Your SurfSense Business license has renewed"
    assert mail.attachments[0].content == b"CERT-lic-firm"
    assert "Acme Accounting LLP" in mail.text_body


async def test_a_retried_renewal_changes_nothing_and_mails_nothing_again(
    env: Billing,
) -> None:
    """Stripe redelivers events; the expiry is read from the subscription, so it is the same."""
    firm_license(env)
    renewed(env, "sub_firm", price=BUSINESS_PRICE)

    await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))
    await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))

    assert len(env.keygen.writes("lic-firm")) == 1
    assert len(env.mail) == 1


async def test_the_first_invoice_before_the_checkout_event_writes_nothing(
    env: Billing,
) -> None:
    """The checkout's own event mints the license with this period's expiry."""
    env.stripe.subscriptions["sub_new"] = subscription(
        "sub_new", period_end=int(YEAR_ONE_END.timestamp()), price=BUSINESS_PRICE
    )

    response = await post_event(paid("in_first", "sub_new", "subscription_create"))

    assert response.status_code == 200
    assert env.keygen.licenses == {}
    assert env.mail == []


async def test_a_renewal_also_takes_the_people_the_firm_confirmed(
    env: Billing,
) -> None:
    firm_license(env, people=3)
    renewed(env, "sub_firm", people=5, price=BUSINESS_PRICE)

    await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))

    assert env.keygen.licenses["lic-firm"]["attributes"]["maxUsers"] == 5


async def test_a_suspended_license_is_extended_but_never_mailed(env: Billing) -> None:
    """A refunded firm whose subscription went on charging gets no fresh file."""
    firm_license(env, status="SUSPENDED")
    renewed(env, "sub_firm", price=BUSINESS_PRICE)

    await post_event(paid("in_year2", "sub_firm", "subscription_cycle"))

    assert expiry_of(env, "lic-firm") == YEAR_TWO_END + GRACE
    assert env.mail == []
    assert not any(r.url.path.endswith("/check-out") for r in env.keygen.requests)


# the Individual subscriptions sold before stripeSubscriptionId -----------------


def individual_bought_before_the_change(env: Billing) -> None:
    """Sold through the Individual Payment Link: no stripeSubscriptionId on it."""
    env.keygen.add(
        "lic-solo",
        policy="policy-individual",
        expiry=(YEAR_ONE_END - timedelta(days=1)).isoformat(),
        plan="individual",
        email="solo@example.com",
        checkoutSessionId="cs_solo",
        stripeCustomerId="cus_solo",
    )
    env.stripe.sessions["cs_solo"] = {
        "id": "cs_solo",
        "object": "checkout.session",
        "mode": "subscription",
        "subscription": "sub_solo",
    }


async def test_an_individual_subscription_renews_on_its_own_key(env: Billing) -> None:
    individual_bought_before_the_change(env)
    renewed(env, "sub_solo", price=INDIVIDUAL_PRICE)

    await post_event(paid("in_solo2", "sub_solo", "subscription_cycle"))

    assert list(env.keygen.licenses) == ["lic-solo"]
    assert expiry_of(env, "lic-solo") == YEAR_TWO_END + GRACE
    # Found once through its checkout session; directly from now on.
    metadata = env.keygen.licenses["lic-solo"]["attributes"]["metadata"]
    assert metadata["stripeSubscriptionId"] == "sub_solo"
    assert metadata["checkoutSessionId"] == "cs_solo"
    assert metadata["plan"] == "individual"


async def test_an_individual_renewal_mails_the_individual_copy(env: Billing) -> None:
    individual_bought_before_the_change(env)
    renewed(env, "sub_solo", price=INDIVIDUAL_PRICE)

    await post_event(paid("in_solo2", "sub_solo", "subscription_cycle"))

    (mail,) = env.mail
    assert mail.subject == "Your SurfSense license has renewed"
    assert "Business" not in mail.text_body


async def test_an_individual_renewal_never_touches_its_price_or_count(
    env: Billing,
) -> None:
    """Its price is Stripe's alone, and a seat count is only Business's."""
    individual_bought_before_the_change(env)
    renewed(env, "sub_solo", people=1, price=INDIVIDUAL_PRICE)

    await post_event(paid("in_solo2", "sub_solo", "subscription_cycle"))

    (patch,) = env.keygen.writes("lic-solo")
    assert set(json.loads(patch.content)["data"]["attributes"]) == {
        "expiry",
        "metadata",
    }
    assert not any(method == "POST" for method, _ in env.stripe.calls)


# customer.subscription.updated -------------------------------------------------


async def test_a_seat_change_moves_the_people_count_and_nothing_else(
    env: Billing,
) -> None:
    firm_license(env, people=3)
    moved = subscription(
        "sub_firm",
        period_end=int(YEAR_ONE_END.timestamp()),
        quantity=5,
        price=BUSINESS_PRICE,
    )

    await post_event(event("customer.subscription.updated", moved))

    (patch,) = env.keygen.writes("lic-firm")
    assert json.loads(patch.content)["data"]["attributes"] == {"maxUsers": 5}


async def test_a_new_period_before_its_payment_does_not_extend_the_license(
    env: Billing,
) -> None:
    """Stripe advances the period before the renewal is paid; only invoice.paid extends."""
    firm_license(env, people=3)
    advanced = subscription(
        "sub_firm",
        period_end=int(YEAR_TWO_END.timestamp()),
        quantity=3,
        price=BUSINESS_PRICE,
    )

    await post_event(event("customer.subscription.updated", advanced))

    assert env.keygen.writes("lic-firm") == []
    assert expiry_of(env, "lic-firm") == YEAR_ONE_END + GRACE


async def test_an_individual_subscription_update_changes_nothing(env: Billing) -> None:
    env.keygen.add(
        "lic-solo",
        policy="policy-individual",
        plan="individual",
        email="solo@example.com",
        stripeSubscriptionId="sub_solo",
    )
    moved = subscription(
        "sub_solo", period_end=int(YEAR_ONE_END.timestamp()), quantity=2
    )

    await post_event(event("customer.subscription.updated", moved))

    assert env.keygen.writes("lic-solo") == []


# customer.subscription.deleted -------------------------------------------------


async def test_an_ended_subscription_lets_the_license_lapse_untouched(
    env: Billing,
) -> None:
    """Its expiry already ends the last paid year plus the grace; nothing suspends it."""
    firm_license(env)
    ended = subscription(
        "sub_firm", period_end=int(YEAR_ONE_END.timestamp()), quantity=3
    )
    ended["status"] = "canceled"

    response = await post_event(event("customer.subscription.deleted", ended))

    assert response.status_code == 200
    assert env.keygen.writes("lic-firm") == []
    assert env.keygen.licenses["lic-firm"]["attributes"]["status"] == "ACTIVE"
    assert expiry_of(env, "lic-firm") == YEAR_ONE_END + GRACE
