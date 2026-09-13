"""HTTP wiring for the three unauthenticated license routes.

These prove the product decision holds at the edge: no route takes a session,
none reads the user table, and none touches Postgres. That is also why they are
unit tests -- the whole license path runs with the database dependency
overridden by a stub that is never used. If one of these ever starts needing a
real session, the design has regressed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.app import app
from app.config import config
from app.db import get_async_session
from app.mailer.protocol import MailerRejectedError, MailerUnavailableError
from app.routes import stripe_routes
from app.services import license_service
from tests.utils.fake_keygen import FakeKeygen
from tests.utils.fake_mailer import FakeMailer

pytestmark = pytest.mark.unit


class _FakeWebhookStripeClient:
    """Verifies nothing and returns the event under test."""

    def __init__(self, event):
        self.event = event
        self.v1 = SimpleNamespace(
            customers=SimpleNamespace(update=lambda *a, **k: None),
            checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=self._retrieve)),
        )

    def construct_event(self, payload, signature, secret):
        return self.event

    def _retrieve(self, session_id, params=None):
        return self.event.data.object


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
        customer="cus_license_1",
        customer_details=SimpleNamespace(email=email),
        line_items=None,
    )


@pytest_asyncio.fixture
async def client():
    async def override_session():
        # The license path never touches it; the Stripe route only declares it.
        yield None

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
def fake_keygen(monkeypatch):
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    monkeypatch.setattr(config, "KEYGEN_POLICY_INDIVIDUAL", "policy-individual")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TEAM", "policy-team")
    return FakeKeygen().install(monkeypatch, license_service.keygen)


@pytest.fixture
def mailer(monkeypatch):
    """Mail enabled, so routes do not short-circuit on 503."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    fake = FakeMailer()
    monkeypatch.setattr(license_service, "get_mailer", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """Bypassed here; the buckets have their own test in tests/unit/services."""

    async def _allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.routes.license_routes.enforce_license_rate_limit", _allow)


@pytest.fixture(autouse=True)
def _no_redis_locks(monkeypatch):
    @asynccontextmanager
    async def _noop(_key, **_kwargs):
        yield True

    monkeypatch.setattr(license_service, "license_lock", _noop)


@pytest.fixture(autouse=True)
def _trial_enabled(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "LICENSE_TRIAL_EXPIRY_FLOOR", "")


async def _webhook(client, monkeypatch, event_type, obj):
    event = SimpleNamespace(
        id="evt_1", type=event_type, data=SimpleNamespace(object=obj)
    )
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        stripe_routes, "get_stripe_client", lambda: _FakeWebhookStripeClient(event)
    )
    return await client.post(
        "/api/v1/stripe/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "sig"},
    )


# -- purchase --------------------------------------------------------------


async def test_purchase_issues_once_and_is_downloadable_by_session(
    client, monkeypatch, fake_keygen, mailer
):
    """Two webhook deliveries must not mint two licenses; there is no unique row."""
    session = _checkout_session()

    first = await _webhook(client, monkeypatch, "checkout.session.completed", session)
    second = await _webhook(client, monkeypatch, "checkout.session.completed", session)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_keygen.licenses) == 1

    response = await client.get("/api/v1/license/file?session_id=cs_license_1")

    assert response.status_code == 200
    assert response.text.startswith("-----BEGIN LICENSE FILE-----")
    assert "surfsense.lic" in response.headers["content-disposition"]


async def test_purchase_emails_the_file(client, monkeypatch, fake_keygen, mailer):
    await _webhook(
        client, monkeypatch, "checkout.session.completed", _checkout_session()
    )

    assert mailer.only().to == "buyer@example.com"
    assert mailer.only().subject == "Your SurfSense license"
    assert mailer.only().attachments[0].filename == "surfsense.lic"


async def test_a_failed_email_does_not_fail_the_purchase(
    client, monkeypatch, fake_keygen
):
    """The license exists and the success page serves it; a retry could duplicate."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    monkeypatch.setattr(
        license_service,
        "get_mailer",
        lambda: FakeMailer(raises=MailerUnavailableError("down")),
    )

    response = await _webhook(
        client, monkeypatch, "checkout.session.completed", _checkout_session()
    )

    assert response.status_code == 200
    assert len(fake_keygen.licenses) == 1


async def test_the_success_page_fulfils_when_the_webhook_has_not_landed(
    client, monkeypatch, fake_keygen, mailer
):
    """The buyer arrives seconds after paying; the webhook can take 30s."""
    session = _checkout_session(session_id="cs_race")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(
        "app.routes.license_routes.get_stripe_client",
        lambda: _FakeWebhookStripeClient(
            SimpleNamespace(data=SimpleNamespace(object=session))
        ),
    )

    response = await client.get("/api/v1/license/file?session_id=cs_race")

    assert response.status_code == 200
    assert len(fake_keygen.licenses) == 1


async def test_download_requires_a_session_id(client, fake_keygen):
    """The removed fallback was 'the signed-in user's license'. Nothing replaces it."""
    response = await client.get("/api/v1/license/file")

    assert response.status_code == 422


async def test_download_of_an_unknown_session_is_404(client, monkeypatch, fake_keygen):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")

    response = await client.get("/api/v1/license/file?session_id=cs_nope")

    assert response.status_code == 404


async def test_a_refund_suspends_the_license(client, monkeypatch, fake_keygen, mailer):
    await _webhook(
        client, monkeypatch, "checkout.session.completed", _checkout_session()
    )
    issued = next(iter(fake_keygen.licenses))

    response = await _webhook(
        client,
        monkeypatch,
        "charge.refunded",
        SimpleNamespace(id="ch_1", customer="cus_license_1"),
    )

    assert response.status_code == 200
    assert fake_keygen.suspended == [issued]


async def test_a_non_license_checkout_is_still_ignored(
    client, monkeypatch, fake_keygen, mailer
):
    response = await _webhook(
        client,
        monkeypatch,
        "checkout.session.completed",
        _checkout_session(purchase_type="something_else"),
    )

    assert response.status_code == 200
    assert fake_keygen.licenses == {}


# -- resend ----------------------------------------------------------------


async def test_resend_mails_every_license_for_the_address(client, fake_keygen, mailer):
    await license_service.issue_license(
        plan="individual", email="buyer@example.com", source="stripe"
    )
    await license_service.issue_license(
        plan="team", email="buyer@example.com", max_users=5, source="stripe"
    )

    response = await client.post(
        "/api/v1/license/resend", json={"email": "Buyer@Example.com"}
    )

    assert response.status_code == 200
    assert len(mailer.only().attachments) == 2
    assert "resent" in mailer.only().subject


async def test_resend_answers_identically_for_an_unknown_address(
    client, fake_keygen, mailer
):
    """Otherwise the endpoint is an oracle for who is a customer."""
    await license_service.issue_license(
        plan="individual", email="buyer@example.com", source="stripe"
    )

    hit = await client.post(
        "/api/v1/license/resend", json={"email": "buyer@example.com"}
    )
    miss = await client.post(
        "/api/v1/license/resend", json={"email": "nobody@example.com"}
    )

    assert hit.status_code == miss.status_code == 200
    assert hit.json() == miss.json()
    assert len(mailer.sent) == 1


async def test_resend_hides_a_rejected_recipient(client, monkeypatch, fake_keygen):
    """A bounce would otherwise confirm the address is a customer."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    monkeypatch.setattr(
        license_service,
        "get_mailer",
        lambda: FakeMailer(raises=MailerRejectedError("550")),
    )
    await license_service.issue_license(
        plan="individual", email="buyer@example.com", source="stripe"
    )

    response = await client.post(
        "/api/v1/license/resend", json={"email": "buyer@example.com"}
    )

    assert response.status_code == 200


async def test_resend_refuses_when_mail_is_disabled(client, monkeypatch, fake_keygen):
    """Disabled mail must refuse, not report a send that never happens."""
    monkeypatch.setattr(config, "SMTP_ENABLED", False)

    response = await client.post(
        "/api/v1/license/resend", json={"email": "buyer@example.com"}
    )

    assert response.status_code == 503
    assert fake_keygen.checkouts == []


async def test_resend_rejects_a_malformed_address(client, fake_keygen, mailer):
    response = await client.post("/api/v1/license/resend", json={"email": "not-email"})

    assert response.status_code == 422


# -- trial -----------------------------------------------------------------


async def test_trial_issues_once_and_mails_it(client, fake_keygen, mailer):
    first = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )
    second = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(fake_keygen.licenses) == 1
    assert "trial" in mailer.only().subject


async def test_the_trial_file_is_never_returned_over_http(client, fake_keygen, mailer):
    """Requiring a real inbox is what makes one-trial-per-email mean anything."""
    response = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )

    assert "BEGIN LICENSE FILE" not in response.text


async def test_trial_is_dark_until_enabled(client, monkeypatch, fake_keygen, mailer):
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", False)

    response = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )

    assert response.status_code == 404


async def test_trial_rejects_disposable_domains(client, fake_keygen, mailer):
    response = await client.post(
        "/api/v1/license/trial", json={"email": "person@mailinator.com"}
    )

    assert response.status_code == 400
    assert fake_keygen.licenses == {}


async def test_trial_refuses_when_mail_is_disabled(client, monkeypatch, fake_keygen):
    monkeypatch.setattr(config, "SMTP_ENABLED", False)

    response = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )

    assert response.status_code == 503
    assert fake_keygen.licenses == {}


async def test_trial_says_so_when_the_license_exists_but_mail_failed(
    client, monkeypatch, fake_keygen
):
    """The address is now burned; telling the user only 'error' would be a lie."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    monkeypatch.setattr(
        license_service,
        "get_mailer",
        lambda: FakeMailer(raises=MailerUnavailableError("down")),
    )

    response = await client.post(
        "/api/v1/license/trial", json={"email": "person@example.com"}
    )

    assert response.status_code == 503
    assert "resend" in response.json()["detail"].lower()
    assert len(fake_keygen.licenses) == 1
