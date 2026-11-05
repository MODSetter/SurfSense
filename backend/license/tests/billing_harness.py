"""The webhook as Stripe drives it: Keygen and Stripe faked at their transports, mail caught at the mailer.

Everything between the signed event and those three seams runs as written.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx2
import pytest
from fastapi import FastAPI

from license import keygen, stripe_webhook
from license.email import deliver
from license.settings import config
from license.tests.stripe_fake import SECRET, FakeStripe, signed
from license.tests.test_license_routes import FakeKeygen
from mailer.protocol import OutboundEmail

BUSINESS_PRICE = "price_business"
INDIVIDUAL_PRICE = "price_individual"
PORTAL = "https://billing.stripe.com/p/login/test_portal"


class SentMail(list[OutboundEmail]):
    async def send(self, message: OutboundEmail) -> None:
        self.append(message)


@dataclass
class Billing:
    keygen: FakeKeygen
    stripe: FakeStripe
    mail: SentMail = field(default_factory=SentMail)

    def created(self) -> list[dict]:
        """The licenses Keygen holds, in the order they were created."""
        return list(self.keygen.licenses.values())


def billing(monkeypatch: pytest.MonkeyPatch) -> Billing:
    env = Billing(keygen=FakeKeygen(), stripe=FakeStripe())

    @asynccontextmanager
    async def http(client=None):
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(env.keygen.handle)
        ) as session:
            yield session

    monkeypatch.setattr(keygen, "_http", http)
    for name, value in {
        "KEYGEN_ACCOUNT_ID": "acct",
        "KEYGEN_API_TOKEN": "product-token",
        "KEYGEN_API_URL": "",
        "KEYGEN_HOST": "",
        "KEYGEN_POLICY_TRIAL": "policy-trial",
        "KEYGEN_POLICY_INDIVIDUAL": "policy-individual",
        "KEYGEN_POLICY_TEAM": "policy-team",
        "KEYGEN_POLICY_BUSINESS": "policy-business",
        "KEYGEN_POLICY_BUSINESS_TRIAL": "policy-business-trial",
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_WEBHOOK_SECRET": SECRET,
        "STRIPE_PRICE_LICENSE_INDIVIDUAL": INDIVIDUAL_PRICE,
        "STRIPE_PRICE_LICENSE_TEAM": "",
        "STRIPE_PRICE_LICENSE_BUSINESS": BUSINESS_PRICE,
        "STRIPE_CUSTOMER_PORTAL_URL": PORTAL,
    }.items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr(stripe_webhook, "get_stripe_client", env.stripe.client)
    monkeypatch.setattr(deliver, "is_mail_enabled", lambda: True)
    monkeypatch.setattr(deliver, "get_mailer", lambda: env.mail)
    return env


async def post_event(
    payload: bytes,
    headers: dict[str, str] | None = None,
    *,
    raise_app_exceptions: bool = True,
):
    """With ``raise_app_exceptions=False``, a failed handler answers as Stripe sees it: a 500."""
    app = FastAPI()
    app.include_router(stripe_webhook.router)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(
            app=app, raise_app_exceptions=raise_app_exceptions
        ),
        base_url="http://portal",
    ) as client:
        return await client.post(
            "/stripe/webhook", content=payload, headers=headers or signed(payload)
        )
