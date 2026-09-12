from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.config import config
from app.db import LicensePurchase, get_async_session
from app.routes import stripe_routes
from app.services import keygen
from app.users import get_jwt_strategy

pytestmark = pytest.mark.integration

_CERTIFICATE = "-----BEGIN LICENSE FILE-----\ncontract-bytes\n"


class _FakeWebhookStripeClient:
    def __init__(self, event):
        self.event = event

    def construct_event(self, payload, signature, secret):
        return self.event


def _checkout_session(
    *,
    session_id: str = "cs_license_1",
    purchase_type: str = "license",
    plan: str = "team",
    quantity: str = "12",
    email: str = "buyer@example.com",
):
    return SimpleNamespace(
        id=session_id,
        mode="payment",
        payment_status="paid",
        metadata={
            "purchase_type": purchase_type,
            "plan": plan,
            "quantity": quantity,
        },
        customer_details=SimpleNamespace(email=email),
    )


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def mocked_keygen(monkeypatch):
    create = AsyncMock(return_value="keygen-license-1")
    checkout = AsyncMock(return_value=_CERTIFICATE)
    monkeypatch.setattr(keygen, "create_license", create)
    monkeypatch.setattr(keygen, "checkout_license", checkout)
    return create, checkout


async def _set_session_cookie(client: httpx.AsyncClient, user) -> None:
    token = await get_jwt_strategy().write_token(user)
    client.cookies.set(config.SESSION_COOKIE_NAME, token)


async def test_license_webhook_is_idempotent_and_downloads_by_session(
    client,
    db_session,
    mocked_keygen,
    monkeypatch,
):
    checkout_session = _checkout_session()
    event = SimpleNamespace(
        id="evt_license_1",
        type="checkout.session.completed",
        data=SimpleNamespace(object=checkout_session),
    )
    monkeypatch.setattr(stripe_routes.config, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        stripe_routes,
        "get_stripe_client",
        lambda: _FakeWebhookStripeClient(event),
    )

    for _ in range(2):
        response = await client.post(
            "/api/v1/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "test-signature"},
        )
        assert response.status_code == 200, response.text

    create, checkout = mocked_keygen
    create.assert_awaited_once_with("team", "buyer@example.com", 12)
    checkout.assert_awaited_once_with("keygen-license-1")
    rows = (await db_session.execute(select(LicensePurchase))).scalars().all()
    assert len(rows) == 1
    assert rows[0].plan == "team"
    assert rows[0].max_users == 12

    download = await client.get(
        "/api/v1/license/file",
        params={"session_id": checkout_session.id},
    )
    assert download.status_code == 200
    assert download.text == _CERTIFICATE
    assert (
        download.headers["content-disposition"]
        == 'attachment; filename="surfsense.lic"'
    )


async def test_license_file_without_session_requires_auth(client):
    response = await client.get("/api/v1/license/file")
    assert response.status_code == 401


async def test_signed_in_user_downloads_latest_matching_license(
    client,
    db_session,
    db_user,
):
    db_session.add(
        LicensePurchase(
            stripe_checkout_session_id=None,
            email=db_user.email.upper(),
            plan="individual",
            max_users=None,
            source="enterprise",
            keygen_license_id="keygen-auth-download",
            certificate=_CERTIFICATE,
        )
    )
    await db_session.commit()
    await _set_session_cookie(client, db_user)

    response = await client.get("/api/v1/license/file")
    assert response.status_code == 200
    assert response.text == _CERTIFICATE


async def test_signed_in_user_gets_404_when_email_does_not_match(
    client,
    db_session,
    db_user,
):
    db_session.add(
        LicensePurchase(
            stripe_checkout_session_id=None,
            email="someone-else@example.com",
            plan="individual",
            max_users=None,
            source="enterprise",
            keygen_license_id="keygen-other-email",
            certificate=_CERTIFICATE,
        )
    )
    await db_session.commit()
    await _set_session_cookie(client, db_user)

    response = await client.get("/api/v1/license/file")
    assert response.status_code == 404


async def test_trial_is_dark_then_issues_only_once(
    client,
    db_user,
    mocked_keygen,
    monkeypatch,
):
    token = await get_jwt_strategy().write_token(db_user)
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", False)
    dark = await client.post("/api/v1/license/trial", headers=headers)
    assert dark.status_code == 404

    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    issued = await client.post("/api/v1/license/trial", headers=headers)
    assert issued.status_code == 200
    assert issued.text == _CERTIFICATE

    repeated = await client.post("/api/v1/license/trial", headers=headers)
    assert repeated.status_code == 409
    mocked_keygen[0].assert_awaited_once()


async def test_non_license_webhook_remains_ignored(
    client,
    mocked_keygen,
    monkeypatch,
):
    event = SimpleNamespace(
        id="evt_other_1",
        type="checkout.session.completed",
        data=SimpleNamespace(
            object=_checkout_session(
                session_id="cs_other",
                purchase_type="subscription",
            )
        ),
    )
    monkeypatch.setattr(stripe_routes.config, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        stripe_routes,
        "get_stripe_client",
        lambda: _FakeWebhookStripeClient(event),
    )

    response = await client.post(
        "/api/v1/stripe/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "test-signature"},
    )
    assert response.status_code == 200
    mocked_keygen[0].assert_not_awaited()
