"""The mail check both license POST routes run before touching Keygen."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import config
from app.license import keygen
from app.license.router import router
from app.mailer import reset_mailer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_mailer_cache():
    reset_mailer()
    yield
    reset_mailer()


@pytest.fixture
def keygen_requests(monkeypatch) -> list[httpx.Request]:
    """Every request that reaches Keygen. Answers 500 so nothing gets issued."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500)

    @asynccontextmanager
    async def fake_http(client=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            yield http

    monkeypatch.setattr(keygen, "_http", fake_http)
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    return seen


@pytest.fixture
def smtp_misconfigured(monkeypatch):
    """Mail switched on, but with no host: the mailer cannot be built."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 0)


def _client() -> AsyncClient:
    app = FastAPI()
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_trial_is_never_created_when_smtp_is_misconfigured(
    smtp_misconfigured, keygen_requests
):
    """A trial that cannot be mailed would burn the address for nothing."""
    async with _client() as client:
        response = await client.post(
            "/license/trial", json={"email": "someone@example.com"}
        )

    assert response.status_code == 503
    assert keygen_requests == []


async def test_resend_refuses_before_any_lookup_when_smtp_is_misconfigured(
    smtp_misconfigured, keygen_requests
):
    """Answering after the lookup would vary with whether the address is a customer."""
    async with _client() as client:
        response = await client.post(
            "/license/resend", json={"email": "someone@example.com"}
        )

    assert response.status_code == 503
    assert keygen_requests == []


async def test_a_valid_smtp_configuration_reaches_keygen(
    monkeypatch, smtp_misconfigured, keygen_requests
):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.test")

    async with _client() as client:
        await client.post("/license/trial", json={"email": "someone@example.com"})

    assert keygen_requests != []
