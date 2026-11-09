"""Stripe's webhook, signed as Stripe signs it, with Keygen faked at its transport."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager

import httpx2
import pytest
from fastapi import FastAPI

from license import keygen, stripe_webhook
from license.settings import config
from license.tests.test_license_routes import FakeKeygen
from mailer.settings import config as mail_config

pytestmark = pytest.mark.unit

SECRET = "whsec_test"


def signed(payload: bytes, secret: str = SECRET) -> dict[str, str]:
    """Stripe's scheme: an HMAC-SHA256 of `<timestamp>.<payload>` under the endpoint's secret."""
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}"}


def paid_license_checkout(session_id: str) -> bytes:
    return json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "object": "checkout.session",
                    "payment_status": "paid",
                    "metadata": {"purchase_type": "license", "plan": "individual"},
                    "customer_details": {"email": "buyer@example.com"},
                    "customer": None,
                    "amount_total": 6000,
                    "currency": "usd",
                }
            },
        }
    ).encode()


@pytest.fixture
def keygen_store(monkeypatch: pytest.MonkeyPatch) -> FakeKeygen:
    fake = FakeKeygen()

    @asynccontextmanager
    async def http(client=None):
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake.handle)
        ) as session:
            yield session

    monkeypatch.setattr(keygen, "_http", http)
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_API_URL", "")
    monkeypatch.setattr(config, "KEYGEN_HOST", "")
    monkeypatch.setattr(config, "KEYGEN_POLICY_INDIVIDUAL", "policy-individual")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_unused")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", SECRET)
    # The purchase mail is best effort and off here; the license is what is asserted.
    monkeypatch.setattr(mail_config, "SMTP_ENABLED", False)
    return fake


async def post_event(payload: bytes, headers: dict[str, str]) -> httpx2.Response:
    app = FastAPI()
    app.include_router(stripe_webhook.router)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        return await client.post("/stripe/webhook", content=payload, headers=headers)


async def test_a_signed_license_purchase_creates_its_license_in_keygen(
    keygen_store: FakeKeygen, posthog_events
) -> None:
    response = await post_event(
        paid_license_checkout("cs_paid"), signed(paid_license_checkout("cs_paid"))
    )

    assert response.status_code == 200
    created = [
        r
        for r in keygen_store.requests
        if r.method == "POST" and r.url.path.endswith("/licenses")
    ]
    assert len(created) == 1
    metadata = json.loads(created[0].content)["data"]["attributes"]["metadata"]
    assert metadata["email"] == "buyer@example.com"
    assert metadata["checkoutSessionId"] == "cs_paid"


async def test_an_event_signed_with_another_secret_is_refused(
    keygen_store: FakeKeygen,
) -> None:
    payload = paid_license_checkout("cs_forged")

    response = await post_event(payload, signed(payload, secret="whsec_someone_else"))

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Stripe webhook signature."}
    assert keygen_store.requests == []
