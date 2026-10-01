"""The portal's unauthenticated routes, driven over HTTP.

Keygen and the mailer are faked at the router's own imports; the token bucket
is the real one, on its per-process fallback. Resend's single answer is the
point of the route, so what it found is asserted from the mailer side, never
from the response.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.config import config
from app.gateway import ratelimit
from app.license import router as license_router
from app.license.models import TrialAlreadyClaimedError
from app.mailer import MailerRejectedError, MailerUnavailableError

pytestmark = pytest.mark.unit

CERTIFICATE = "-----BEGIN LICENSE FILE-----\nsecret\n-----END LICENSE FILE-----\n"


class Portal:
    """The routes behind a client, and what they asked of Keygen and the mailer."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.mail_enabled = True
        self.customers: dict[str, list[str]] = {}
        self.lookups: list[str] = []
        self.mailed: list[tuple[str, str, list[str]]] = []
        self.deliver_error: Exception | None = None
        self.lookup_error: Exception | None = None
        self.trial_error: Exception | None = None

        monkeypatch.setattr(
            license_router, "is_mail_enabled", lambda: self.mail_enabled
        )
        monkeypatch.setattr(license_router, "get_mailer", lambda: object())
        monkeypatch.setattr(license_router, "certificates_for_email", self._lookup)
        monkeypatch.setattr(license_router, "deliver_licenses", self._deliver)
        monkeypatch.setattr(license_router, "issue_trial_license", self._issue_trial)

    async def _lookup(self, email: str) -> list[str]:
        self.lookups.append(email)
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.customers.get(email, [])

    async def _deliver(
        self, kind: str, *, to: str, certificates: list[str], **_
    ) -> None:
        if self.deliver_error is not None:
            raise self.deliver_error
        self.mailed.append((kind, to, certificates))

    async def _issue_trial(self, email: str) -> SimpleNamespace:
        if self.trial_error is not None:
            raise self.trial_error
        return SimpleNamespace(certificate=CERTIFICATE, keygen_license_id="lic-trial")


@pytest.fixture
def portal(monkeypatch: pytest.MonkeyPatch) -> Portal:
    """Mail on, trials on, generous limits, and an empty in-memory bucket."""

    def redis_down() -> None:
        raise OSError("no Redis in unit tests")

    monkeypatch.setattr(ratelimit, "_redis", redis_down)
    monkeypatch.setattr(ratelimit, "_memory_buckets", {})
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 100)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 100)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 100)
    return Portal(monkeypatch)


async def post(path: str, email: str, ip: str = "203.0.113.1") -> httpx.Response:
    app = FastAPI()
    app.include_router(license_router.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        return await client.post(path, json={"email": email}, headers={"X-Real-IP": ip})


# resend ---------------------------------------------------------------------


async def test_resend_answers_the_same_whether_or_not_the_address_is_a_customer(
    portal: Portal,
) -> None:
    """Anything else would let the route tell a stranger who has bought."""
    portal.customers["buyer@example.com"] = [CERTIFICATE]

    found = await post("/license/resend", "buyer@example.com")
    missing = await post("/license/resend", "stranger@example.com")

    assert (found.status_code, missing.status_code) == (200, 200)
    assert found.json() == missing.json()
    assert portal.mailed == [("resend", "buyer@example.com", [CERTIFICATE])]


async def test_resend_answers_the_same_when_the_mail_server_refuses_the_address(
    portal: Portal,
) -> None:
    """A refusal would confirm the address belongs to a customer."""
    portal.customers["buyer@example.com"] = [CERTIFICATE]
    portal.deliver_error = MailerRejectedError("550 no such user")

    refused = await post("/license/resend", "buyer@example.com")
    missing = await post("/license/resend", "stranger@example.com")

    assert refused.status_code == 200
    assert refused.json() == missing.json()


async def test_resend_is_503_when_mail_is_off_before_any_lookup(portal: Portal) -> None:
    """Checked first, so the refusal says nothing about the address."""
    portal.mail_enabled = False

    reply = await post("/license/resend", "buyer@example.com")

    assert reply.status_code == 503
    assert portal.lookups == []


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("keygen down"), None],
    ids=["keygen", "mail outage"],
)
async def test_resend_is_503_when_keygen_or_the_mailer_is_down(
    portal: Portal, failure: Exception | None
) -> None:
    """An outage is said plainly; it does not depend on who the address is."""
    portal.customers["buyer@example.com"] = [CERTIFICATE]
    if failure is None:
        portal.deliver_error = MailerUnavailableError("timed out")
    else:
        portal.lookup_error = failure

    reply = await post("/license/resend", "buyer@example.com")

    assert reply.status_code == 503


# trial ----------------------------------------------------------------------


async def test_trial_is_404_when_trials_are_off(portal: Portal, monkeypatch) -> None:
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", False)

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 404


async def test_trial_is_400_for_a_disposable_address(portal: Portal) -> None:
    """One trial per inbox means nothing for an inbox anyone can open."""
    reply = await post("/license/trial", "new@mailinator.com")

    assert reply.status_code == 400
    assert portal.mailed == []


async def test_trial_is_409_for_an_address_that_already_claimed_one(
    portal: Portal,
) -> None:
    portal.trial_error = TrialAlreadyClaimedError()

    reply = await post("/license/trial", "again@example.com")

    assert reply.status_code == 409


async def test_trial_is_503_when_keygen_is_down(portal: Portal) -> None:
    """Pointed at resend, which finds a trial created before the failure."""
    portal.trial_error = RuntimeError("keygen down")

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 503
    assert "resend" in reply.json()["detail"]


async def test_trial_is_503_when_mail_is_down_and_says_the_trial_exists(
    portal: Portal,
) -> None:
    """The address is spent, so the caller is told where the file is."""
    portal.deliver_error = MailerUnavailableError("timed out")

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 503
    assert "created" in reply.json()["detail"]


async def test_trial_mails_the_file_and_never_returns_it(portal: Portal) -> None:
    """Delivery to a real inbox is what makes one trial per address mean anything."""
    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 200
    assert CERTIFICATE not in reply.text
    assert "secret" not in reply.text
    assert portal.mailed == [("trial", "new@example.com", [CERTIFICATE])]


# rate limits ----------------------------------------------------------------


async def test_the_ip_bucket_bites_across_addresses(
    portal: Portal, monkeypatch
) -> None:
    """One caller cycling addresses is still one caller."""
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 2)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 0)

    codes = [
        (await post("/license/resend", f"user{n}@example.com")).status_code
        for n in range(3)
    ]

    assert codes == [200, 200, 429]


async def test_the_email_bucket_bites_across_callers(
    portal: Portal, monkeypatch
) -> None:
    """Folded, so a +tag is the same address; spread over IPs, still one address."""
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 2)

    codes = [
        (await post("/license/trial", email, ip=f"203.0.113.{n}")).status_code
        for n, email in enumerate(
            ["new@example.com", "new+a@example.com", "new+b@example.com"]
        )
    ]

    assert codes[2] == 429


async def test_a_limit_of_zero_turns_its_bucket_off(
    portal: Portal, monkeypatch
) -> None:
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 0)

    codes = {
        (await post("/license/resend", "buyer@example.com")).status_code
        for _ in range(20)
    }

    assert codes == {200}
