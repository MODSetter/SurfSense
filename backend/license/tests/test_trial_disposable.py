"""The trial route refuses a disposable address before any license exists."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx2
import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from license import keygen
from license.router import router
from license.settings import config
from mailer import reset_mailer
from mailer.settings import config as mail_config

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _trial_open_with_mail(monkeypatch):
    """Every check before the disposable one passes."""
    reset_mailer()
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    monkeypatch.setattr(mail_config, "SMTP_ENABLED", True)
    monkeypatch.setattr(mail_config, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(mail_config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(mail_config, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(
        config, "LICENSE_DISPOSABLE_EMAIL_DOMAINS", "xn--bcher-kva.example"
    )
    yield
    reset_mailer()


@pytest.fixture
def keygen_requests(monkeypatch) -> list[httpx2.Request]:
    """Every request that reaches Keygen. Answers 500 so nothing gets issued."""
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(500)

    @asynccontextmanager
    async def fake_http(client=None):
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http:
            yield http

    monkeypatch.setattr(keygen, "_http", fake_http)
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    return seen


async def _claim_trial(email: str) -> httpx2.Response:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/license/trial", json={"email": email})


@pytest.mark.parametrize(
    "email",
    [
        # Community-listed through its parent domain, typed in capitals.
        "Someone@Inbox.Mailinator.COM",
        # Listed in punycode and typed that way; `EmailStr` hands over Unicode.
        "someone@xn--bcher-kva.example",
    ],
)
async def test_a_disposable_address_is_refused_before_keygen(email, keygen_requests):
    response = await _claim_trial(email)

    assert response.status_code == 400
    assert keygen_requests == []


async def test_a_permanent_address_goes_on_to_keygen(keygen_requests):
    """The control: the same setup lets a real address through to issuing."""
    await _claim_trial("someone@gmail.com")

    assert keygen_requests != []
