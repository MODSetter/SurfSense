from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import keygen
from app.services.license_service import issue_license


@pytest.fixture
def keygen_config(monkeypatch):
    monkeypatch.setattr(keygen.config, "KEYGEN_ACCOUNT_ID", "account-1")
    monkeypatch.setattr(keygen.config, "KEYGEN_API_TOKEN", "token-1")
    monkeypatch.setattr(keygen.config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    monkeypatch.setattr(
        keygen.config,
        "KEYGEN_POLICY_INDIVIDUAL",
        "policy-individual",
    )
    monkeypatch.setattr(keygen.config, "KEYGEN_POLICY_TEAM", "policy-team")


@pytest.mark.asyncio
async def test_keygen_create_and_checkout_payloads(keygen_config):
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/licenses"):
            return httpx.Response(201, json={"data": {"id": "lic-1"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "certificate": "-----BEGIN LICENSE FILE-----\nraw\n",
                    }
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ) as client:
        license_id = await keygen.create_license(
            "team",
            "buyer@example.com",
            12,
            client=client,
        )
        certificate = await keygen.checkout_license(license_id, client=client)

    assert license_id == "lic-1"
    assert certificate == "-----BEGIN LICENSE FILE-----\nraw\n"
    assert requests[0].headers["authorization"] == "Bearer token-1"
    assert requests[0].headers["content-type"] == "application/vnd.api+json"
    create_body = __import__("json").loads(requests[0].content)
    assert create_body["data"]["attributes"] == {
        "metadata": {"plan": "team", "email": "buyer@example.com"},
        "maxUsers": 12,
    }
    assert "owner" not in create_body["data"]["relationships"]
    assert create_body["data"]["relationships"]["policy"]["data"]["id"] == "policy-team"
    assert __import__("json").loads(requests[1].content) == {
        "meta": {"ttl": None},
    }
    assert "encrypt" not in str(requests[1].content)
    assert "include" not in str(requests[1].content)


class _Session:
    def __init__(self):
        self.added = None
        self.flush = AsyncMock()

    def add(self, value):
        self.added = value


@pytest.mark.asyncio
async def test_issue_license_stores_certificate_unchanged(monkeypatch):
    certificate = "-----BEGIN LICENSE FILE-----\nkeep-this-format\n"
    monkeypatch.setattr(
        keygen,
        "create_license",
        AsyncMock(return_value="lic-raw"),
    )
    monkeypatch.setattr(
        keygen,
        "checkout_license",
        AsyncMock(return_value=certificate),
    )
    session = _Session()

    purchase = await issue_license(
        session,
        plan="individual",
        email=" Buyer@Example.COM ",
        source="stripe",
        stripe_session_id="cs_1",
    )

    assert purchase is session.added
    assert purchase.email == "buyer@example.com"
    assert purchase.max_users is None
    assert purchase.certificate == certificate
    session.flush.assert_awaited_once()
