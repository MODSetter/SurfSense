"""A Business purchase: Stripe's signed checkout of the yearly per-person price becomes one license."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import FastAPI

from license import router as license_router
from license.tests.billing_harness import (
    BUSINESS_PRICE,
    PORTAL,
    Billing,
    billing,
    post_event,
)
from license.tests.stripe_fake import event, subscription

pytestmark = pytest.mark.unit

PERIOD_END = int(datetime(2027, 11, 3, tzinfo=UTC).timestamp())


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, posthog_events) -> Billing:
    return billing(monkeypatch)


def business_checkout(
    session_id: str = "cs_business",
    *,
    people: int = 3,
    firm: str | None = "  Acme   Accounting LLP ",
) -> dict:
    """What a Payment Link's subscription checkout sends: no metadata, a custom field."""
    custom_fields = (
        [
            {
                "key": "firm",
                "type": "text",
                "label": {"type": "custom", "custom": "Firm name"},
                "text": {"value": firm},
            }
        ]
        if firm is not None
        else []
    )
    return {
        "id": session_id,
        "object": "checkout.session",
        "mode": "subscription",
        "payment_status": "paid",
        "metadata": {},
        "customer": "cus_firm",
        "customer_details": {"email": "Partner@Acme.example"},
        "custom_fields": custom_fields,
        "subscription": "sub_firm",
        "amount_total": 20000 + 12000 * (people - 1),
        "currency": "usd",
        "client_reference_id": "direct",
    }


def stripe_holds(env: Billing, session: dict, *, people: int = 3) -> None:
    env.stripe.sessions[session["id"]] = session
    env.stripe.line_items[session["id"]] = [
        {
            "id": "li_1",
            "object": "item",
            "quantity": people,
            "price": {"id": BUSINESS_PRICE, "object": "price"},
        }
    ]
    env.stripe.subscriptions["sub_firm"] = subscription(
        "sub_firm", period_end=PERIOD_END, quantity=people, price=BUSINESS_PRICE
    )


async def buy(env: Billing, session: dict) -> None:
    response = await post_event(event("checkout.session.completed", session))
    assert response.status_code == 200


async def test_a_business_checkout_creates_one_license_with_the_people_and_the_jobs(
    env: Billing,
) -> None:
    session = business_checkout()
    stripe_holds(env, session)

    await buy(env, session)

    (license_,) = env.created()
    attributes = license_["attributes"]
    assert license_["policy"] == "policy-business"
    assert attributes["metadata"] == {
        "plan": "business",
        "email": "partner@acme.example",
        "firm": "Acme Accounting LLP",
        "jobs": "JOB_QUESTIONNAIRE",
        "stripeSubscriptionId": "sub_firm",
        "checkoutSessionId": "cs_business",
        "stripeCustomerId": "cus_firm",
    }
    # The people count is the license's seat count, as for team keys.
    assert attributes["maxUsers"] == 3


async def test_the_license_ends_with_the_paid_year_plus_the_grace(env: Billing) -> None:
    """It renews on this key, so the first period's end is what the license runs to."""
    session = business_checkout()
    stripe_holds(env, session)

    await buy(env, session)

    (license_,) = env.created()
    expiry = datetime.fromisoformat(license_["attributes"]["expiry"])
    assert expiry == datetime.fromtimestamp(PERIOD_END, UTC) + timedelta(days=30)


async def test_the_file_is_checked_out_without_a_ttl_after_a_validation(
    env: Billing,
) -> None:
    """Keygen checks no status at a product token's check-out, so the server validates first."""
    session = business_checkout()
    stripe_holds(env, session)

    await buy(env, session)

    (license_,) = env.created()
    actions = [
        request.url.path.rsplit("/", 1)[-1]
        for request in env.keygen.requests
        if license_["id"] in request.url.path and "/actions/" in request.url.path
    ]
    assert actions[:2] == ["validate", "check-out"]
    checkout = next(
        request
        for request in env.keygen.requests
        if request.url.path.endswith("/check-out")
    )
    assert json.loads(checkout.content) == {"meta": {"ttl": None}}


async def test_a_checkout_without_the_firm_field_still_issues_the_license(
    env: Billing,
) -> None:
    """A cosmetic field is never a reason to refuse a paid purchase."""
    session = business_checkout(firm=None)
    stripe_holds(env, session)

    await buy(env, session)

    (license_,) = env.created()
    assert "firm" not in license_["attributes"]["metadata"]


async def test_the_purchase_mail_is_the_business_one(env: Billing) -> None:
    session = business_checkout()
    stripe_holds(env, session)

    await buy(env, session)

    (mail,) = env.mail
    assert mail.to == "partner@acme.example"
    assert mail.subject == "Your SurfSense Business license"
    assert "Acme Accounting LLP" in mail.text_body
    assert "3 people" in mail.text_body
    assert PORTAL in mail.text_body
    # The Individual promises do not hold for a license the app refreshes.
    assert "works on every machine" not in mail.text_body
    assert "never contacts a license server" not in mail.text_body


async def test_the_success_page_before_the_webhook_mints_the_same_one_license(
    env: Billing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The buyer lands seconds after paying; the webhook that follows only reads it."""
    session = business_checkout()
    stripe_holds(env, session)
    monkeypatch.setattr(license_router, "get_stripe_client", env.stripe.client)

    app = FastAPI()
    app.include_router(license_router.router)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        reply = await client.get("/license/file", params={"session_id": "cs_business"})
    await buy(env, session)

    (license_,) = env.created()
    assert reply.status_code == 200
    assert reply.text == f"CERT-{license_['id']}"
    assert license_["attributes"]["metadata"]["plan"] == "business"
