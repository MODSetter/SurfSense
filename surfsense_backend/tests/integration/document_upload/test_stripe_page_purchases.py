from __future__ import annotations

from types import SimpleNamespace

import asyncpg
import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.app import app
from app.routes import stripe_routes
from app.tasks.celery_tasks import stripe_reconciliation_task
from tests.conftest import TEST_DATABASE_URL
from tests.utils.helpers import TEST_EMAIL, auth_headers, get_auth_token

pytestmark = pytest.mark.integration

_ASYNCPG_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _execute(query: str, *args) -> None:
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        await conn.execute(query, *args)
    finally:
        await conn.close()


async def _fetchrow(query: str, *args):
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        return await conn.fetchrow(query, *args)
    finally:
        await conn.close()


async def _get_user_id(email: str) -> str:
    row = await _fetchrow('SELECT id FROM "user" WHERE email = $1', email)
    assert row is not None, f"User {email!r} not found"
    return str(row["id"])


async def _get_pages_limit(email: str) -> int:
    row = await _fetchrow('SELECT pages_limit FROM "user" WHERE email = $1', email)
    assert row is not None, f"User {email!r} not found"
    return row["pages_limit"]


@pytest_asyncio.fixture(scope="session")
async def auth_token(_ensure_tables) -> str:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
    ) as client:
        return await get_auth_token(client)


@pytest.fixture(scope="session")
def headers(auth_token: str) -> dict[str, str]:
    return auth_headers(auth_token)


@pytest.fixture(autouse=True)
async def _cleanup_page_purchases():
    await _execute("DELETE FROM page_purchases")
    yield
    await _execute("DELETE FROM page_purchases")


class _FakeCreateStripeClient:
    def __init__(self, checkout_session):
        self.checkout_session = checkout_session
        self.last_params = None
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=SimpleNamespace(create=self._create_session)
            )
        )

    def _create_session(self, *, params):
        self.last_params = params
        return self.checkout_session


class _FakeWebhookStripeClient:
    def __init__(self, event):
        self.event = event
        self.last_payload = None
        self.last_signature = None
        self.last_secret = None

    def construct_event(self, payload, signature, secret):
        self.last_payload = payload
        self.last_signature = signature
        self.last_secret = secret
        return self.event


class _FakeReconciliationStripeClient:
    def __init__(self, checkout_session):
        self.checkout_session = checkout_session
        self.requested_ids = []
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=SimpleNamespace(retrieve=self._retrieve_session)
            )
        )

    def _retrieve_session(self, checkout_session_id: str):
        self.requested_ids.append(checkout_session_id)
        return self.checkout_session


class TestStripeCheckoutSessionCreation:
    async def test_get_status_reflects_backend_toggle(
        self, client, headers, monkeypatch
    ):
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", False)
        disabled_response = await client.get("/api/v1/stripe/status", headers=headers)
        assert disabled_response.status_code == 200, disabled_response.text
        assert disabled_response.json() == {"page_buying_enabled": False}

        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        enabled_response = await client.get("/api/v1/stripe/status", headers=headers)
        assert enabled_response.status_code == 200, enabled_response.text
        assert enabled_response.json() == {"page_buying_enabled": True}

    async def test_create_checkout_session_records_pending_purchase(
        self,
        client,
        headers,
        search_space_id: int,
        monkeypatch,
    ):
        checkout_session = SimpleNamespace(
            id="cs_test_create_123",
            url="https://checkout.stripe.test/cs_test_create_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        fake_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: fake_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 2, "search_space_id": search_space_id},
        )

        assert response.status_code == 200, response.text
        assert response.json() == {"checkout_url": checkout_session.url}
        assert fake_client.last_params is not None
        assert fake_client.last_params["mode"] == "payment"
        assert fake_client.last_params["line_items"] == [
            {"price": "price_pages_1000", "quantity": 2}
        ]
        assert (
            fake_client.last_params["success_url"]
            == f"http://localhost:3000/dashboard/{search_space_id}/purchase-success"
        )
        assert (
            fake_client.last_params["cancel_url"]
            == f"http://localhost:3000/dashboard/{search_space_id}/purchase-cancel"
        )

        purchase = await _fetchrow(
            """
            SELECT quantity, pages_granted, status
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["quantity"] == 2
        assert purchase["pages_granted"] == 2000
        assert purchase["status"] == "PENDING"

    async def test_create_checkout_session_returns_503_when_buying_disabled(
        self,
        client,
        headers,
        search_space_id: int,
        monkeypatch,
    ):
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", False)

        response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 2, "search_space_id": search_space_id},
        )

        assert response.status_code == 503, response.text
        assert (
            response.json()["detail"] == "Page purchases are temporarily unavailable."
        )

        purchase_count = await _fetchrow("SELECT COUNT(*) AS count FROM page_purchases")
        assert purchase_count is not None
        assert purchase_count["count"] == 0


class TestStripeWebhookFulfillment:
    async def test_webhook_grants_pages_once(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=0, pages_limit=100)

        checkout_session = SimpleNamespace(
            id="cs_test_webhook_123",
            url="https://checkout.stripe.test/cs_test_webhook_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        create_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: create_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        create_response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 3, "search_space_id": search_space_id},
        )
        assert create_response.status_code == 200, create_response.text

        initial_limit = await _get_pages_limit(TEST_EMAIL)
        assert initial_limit == 100

        user_id = await _get_user_id(TEST_EMAIL)
        webhook_checkout_session = SimpleNamespace(
            id=checkout_session.id,
            payment_status="paid",
            payment_intent="pi_test_123",
            amount_total=300,
            currency="usd",
            metadata={
                "user_id": user_id,
                "quantity": "3",
                "pages_per_unit": "1000",
            },
        )
        event = SimpleNamespace(
            type="checkout.session.completed",
            data=SimpleNamespace(object=webhook_checkout_session),
        )
        webhook_client = _FakeWebhookStripeClient(event)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: webhook_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        first_response = await client.post(
            "/api/v1/stripe/webhook",
            headers={"Stripe-Signature": "sig_test"},
            content=b"{}",
        )
        assert first_response.status_code == 200, first_response.text

        updated_limit = await _get_pages_limit(TEST_EMAIL)
        assert updated_limit == 3100

        purchase = await _fetchrow(
            """
            SELECT status, amount_total, currency, stripe_payment_intent_id
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["status"] == "COMPLETED"
        assert purchase["amount_total"] == 300
        assert purchase["currency"] == "usd"
        assert purchase["stripe_payment_intent_id"] == "pi_test_123"

        second_response = await client.post(
            "/api/v1/stripe/webhook",
            headers={"Stripe-Signature": "sig_test"},
            content=b"{}",
        )
        assert second_response.status_code == 200, second_response.text

        assert await _get_pages_limit(TEST_EMAIL) == 3100


class TestStripeReconciliation:
    async def test_reconciliation_fulfills_paid_pending_purchase(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=220, pages_limit=150)

        checkout_session = SimpleNamespace(
            id="cs_test_reconcile_paid_123",
            url="https://checkout.stripe.test/cs_test_reconcile_paid_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        create_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: create_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        create_response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 3, "search_space_id": search_space_id},
        )
        assert create_response.status_code == 200, create_response.text
        assert await _get_pages_limit(TEST_EMAIL) == 150

        reconciled_session = SimpleNamespace(
            id=checkout_session.id,
            status="complete",
            payment_status="paid",
            payment_intent="pi_test_reconcile_123",
            amount_total=300,
            currency="usd",
            metadata={},
        )
        reconcile_client = _FakeReconciliationStripeClient(reconciled_session)

        monkeypatch.setattr(
            stripe_reconciliation_task, "get_stripe_client", lambda: reconcile_client
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_LOOKBACK_MINUTES",
            0,
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_BATCH_SIZE",
            20,
        )

        await stripe_reconciliation_task._reconcile_pending_page_purchases()

        assert reconcile_client.requested_ids == [checkout_session.id]
        assert await _get_pages_limit(TEST_EMAIL) == 3220

        purchase = await _fetchrow(
            """
            SELECT status, amount_total, currency, stripe_payment_intent_id
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["status"] == "COMPLETED"
        assert purchase["amount_total"] == 300
        assert purchase["currency"] == "usd"
        assert purchase["stripe_payment_intent_id"] == "pi_test_reconcile_123"

    async def test_reconciliation_marks_expired_pending_purchase_failed(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=0, pages_limit=500)

        checkout_session = SimpleNamespace(
            id="cs_test_reconcile_expired_123",
            url="https://checkout.stripe.test/cs_test_reconcile_expired_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        create_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: create_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        create_response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 1, "search_space_id": search_space_id},
        )
        assert create_response.status_code == 200, create_response.text

        expired_session = SimpleNamespace(
            id=checkout_session.id,
            status="expired",
            payment_status="unpaid",
            payment_intent=None,
            amount_total=100,
            currency="usd",
            metadata={},
        )
        reconcile_client = _FakeReconciliationStripeClient(expired_session)

        monkeypatch.setattr(
            stripe_reconciliation_task, "get_stripe_client", lambda: reconcile_client
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_LOOKBACK_MINUTES",
            0,
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_BATCH_SIZE",
            20,
        )

        await stripe_reconciliation_task._reconcile_pending_page_purchases()

        assert await _get_pages_limit(TEST_EMAIL) == 500

        purchase = await _fetchrow(
            """
            SELECT status
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["status"] == "FAILED"
