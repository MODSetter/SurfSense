"""The portal's unauthenticated routes, driven over HTTP.

Keygen is faked at its transport, so the license code under the routes runs as
written: the trial's folded-address check, its derived id, resend skipping a
suspended license. The mailer is faked at the router, and resend's single
answer is asserted from the mailer side, never from the response. The token
bucket is the real one, on its per-process fallback.
"""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx2
import pytest
from fastapi import FastAPI

from license import keygen
from license import router as license_router
from license import token_bucket as ratelimit
from license.settings import config
from mailer import MailerRejectedError, MailerUnavailableError

pytestmark = pytest.mark.unit


def snake(key: str) -> str:
    """Keygen underscores every filter and metadata key before it compares them."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


class FakeKeygen:
    """The license endpoints the portal calls, over an in-memory store.

    Validation answers as Keygen's does for a user-less, non-strict license:
    BANNED, SUSPENDED, EXPIRED or VALID, and NOT_FOUND with no license. A
    license is answered as JSON:API, its policy under ``relationships``.
    """

    def __init__(self) -> None:
        self.licenses: dict[str, dict] = {}
        self.requests: list[httpx2.Request] = []
        self.down = False
        # Validations answer 200 without meta.code, which Keygen never should.
        self.codeless = False
        # Suspensions answer 503 while every other call works.
        self.refuse_suspend = False
        # License id -> the status its policy change answers: 422 as Keygen
        # refuses an incompatible policy, anything else bare.
        self.refuse_policy_change: dict[str, int] = {}
        # Policy id -> its attributes, as GET /policies/<id> answers them.
        self.policies: dict[str, dict] = {}

    def add(
        self,
        license_id: str,
        status: str = "ACTIVE",
        *,
        policy: str | None = None,
        expiry: str | None = None,
        max_users: int | None = None,
        created: str | None = None,
        **metadata: str,
    ) -> None:
        self.licenses[license_id] = {
            "id": license_id,
            "attributes": {
                "key": f"KEY-{license_id}",
                "metadata": metadata,
                "status": status,
                "expiry": expiry,
                "maxUsers": max_users,
                **({"created": created} if created else {}),
            },
            "policy": policy,
        }

    def writes(self, license_id: str) -> list[httpx2.Request]:
        """Every request that changed this license: an update, a policy change, a suspension."""
        return [
            request
            for request in self.requests
            if license_id in request.url.path
            and (
                request.method in {"PATCH", "PUT"}
                or request.url.path.endswith("/suspend")
            )
        ]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.down:
            return httpx2.Response(503)
        if "/policies/" in request.url.path and request.method == "GET":
            return self._policy(request.url.path.rsplit("/", 1)[1])
        rest = request.url.path.split("/licenses", 1)[1]
        if rest == "" and request.method == "GET":
            return self._list(request)
        if rest == "" and request.method == "POST":
            return self._create(json.loads(request.content)["data"])
        if rest == "/actions/validate-key":
            key = json.loads(request.content)["meta"]["key"]
            return self._validation(
                next(
                    (
                        record
                        for record in self.licenses.values()
                        if record["attributes"]["key"] == key
                    ),
                    None,
                )
            )
        license_id, _, action = rest.strip("/").partition("/")
        record = self.licenses.get(license_id)
        if record is None:
            return httpx2.Response(404)
        if action == "actions/check-out":
            certificate = f"CERT-{license_id}"
            return httpx2.Response(
                200, json={"data": {"attributes": {"certificate": certificate}}}
            )
        if action == "actions/validate":
            return self._validation(record)
        if action == "policy" and request.method == "PUT":
            return self._change_policy(record, json.loads(request.content)["data"])
        if action == "actions/suspend":
            if self.refuse_suspend:
                return httpx2.Response(503)
            if record["attributes"]["status"] == "SUSPENDED":
                # Keygen 1.7.2 refuses to suspend a suspended license.
                return httpx2.Response(
                    422, json={"errors": [{"detail": "is already suspended"}]}
                )
            record["attributes"]["status"] = "SUSPENDED"
        if request.method == "PATCH":
            # Keygen replaces metadata whole, like every other attribute.
            record["attributes"].update(
                json.loads(request.content)["data"]["attributes"]
            )
        return httpx2.Response(200, json={"data": self._answer(record)})

    @staticmethod
    def _answer(record: dict) -> dict:
        """A license as Keygen answers it: JSON:API, its policy a relationship."""
        return {
            "id": record["id"],
            "type": "licenses",
            "attributes": record["attributes"],
            "relationships": {
                "policy": {"data": {"type": "policies", "id": record["policy"]}}
            },
        }

    def _change_policy(self, record: dict, policy: dict) -> httpx2.Response:
        refusal = self.refuse_policy_change.get(record["id"])
        if refusal == 422:
            return httpx2.Response(
                422,
                json={
                    "errors": [
                        {
                            "title": "Unprocessable resource",
                            "detail": "cannot change to a policy with a different scheme",
                            "code": "POLICY_NOT_COMPATIBLE",
                            "source": {"pointer": "/data/relationships/policy"},
                        }
                    ]
                },
            )
        if refusal is not None:
            return httpx2.Response(refusal)
        # The move keeps the expiry, as transferStrategy KEEP_EXPIRY does.
        record["policy"] = policy["id"]
        return httpx2.Response(200, json={"data": self._answer(record)})

    def _policy(self, policy_id: str) -> httpx2.Response:
        attributes = self.policies.get(policy_id)
        if attributes is None:
            return httpx2.Response(404)
        return httpx2.Response(
            200,
            json={
                "data": {"id": policy_id, "type": "policies", "attributes": attributes}
            },
        )

    def _validation(self, record: dict | None) -> httpx2.Response:
        if record is None:
            code = "NOT_FOUND"
        elif record["attributes"]["status"] in {"BANNED", "SUSPENDED"}:
            code = record["attributes"]["status"]
        elif (expiry := record["attributes"].get("expiry")) and datetime.fromisoformat(
            expiry
        ) < datetime.now(UTC):
            code = "EXPIRED"
        else:
            code = "VALID"
        meta = {"valid": code == "VALID", "code": code}
        if self.codeless:
            del meta["code"]
        data = None if record is None else self._answer(record)
        return httpx2.Response(200, json={"data": data, "meta": meta})

    def _list(self, request: httpx2.Request) -> httpx2.Response:
        params = request.url.params
        wanted = {
            snake(key[len("metadata[") : -1]): value
            for key, value in params.multi_items()
            if key.startswith("metadata[")
        }
        policy = params.get("policy")
        found = [
            record
            for record in self.licenses.values()
            if all(
                {snake(k): v for k, v in record["attributes"]["metadata"].items()}.get(
                    k
                )
                == v
                for k, v in wanted.items()
            )
            and (policy is None or record["policy"] == policy)
        ]
        return httpx2.Response(
            200,
            json={
                "data": [
                    self._answer(record)
                    for record in found[: int(params.get("limit", 100))]
                ]
            },
        )

    def _create(self, data: dict) -> httpx2.Response:
        license_id = data.get("id") or f"lic-{len(self.licenses) + 1}"
        if license_id in self.licenses:
            return httpx2.Response(422, json={"errors": [{"code": "ID_CONFLICT"}]})
        policy = data["relationships"]["policy"]["data"]["id"]
        attributes = {
            "expiry": None,
            "maxUsers": None,
            **data["attributes"],
            "key": f"KEY-{license_id}",
            "status": "ACTIVE",
            "created": datetime.now(UTC).isoformat(),
        }
        self.licenses[license_id] = {
            "id": license_id,
            "attributes": attributes,
            "policy": policy,
        }
        return httpx2.Response(
            201, json={"data": self._answer(self.licenses[license_id])}
        )


class Mailer:
    """What the routes asked the mailer to send, and how it answers."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.enabled = True
        self.error: Exception | None = None
        self.sent: list[tuple[str, str, list[str]]] = []
        monkeypatch.setattr(license_router, "is_mail_enabled", lambda: self.enabled)
        monkeypatch.setattr(license_router, "get_mailer", lambda: object())
        monkeypatch.setattr(license_router, "deliver_licenses", self._deliver)

    async def _deliver(
        self, kind: str, *, to: str, certificates: list[str], **_
    ) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((kind, to, certificates))


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
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    return fake


@pytest.fixture
def mailer(monkeypatch: pytest.MonkeyPatch, keygen_store: FakeKeygen) -> Mailer:
    """Mail on, trials on, Stripe off, generous limits, an empty in-memory bucket."""

    def redis_down() -> None:
        raise OSError("no Redis in unit tests")

    monkeypatch.setattr(ratelimit, "_redis", redis_down)
    monkeypatch.setattr(ratelimit, "_memory_buckets", {})
    # A developer's STRIPE_SECRET_KEY would send unknown sessions to live Stripe.
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 100)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 100)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 100)
    return Mailer(monkeypatch)


def portal() -> httpx2.AsyncClient:
    app = FastAPI()
    app.include_router(license_router.router)
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    )


async def post(
    path: str, email: str, ip: str = "203.0.113.1", **fields: object
) -> httpx2.Response:
    async with portal() as client:
        return await client.post(
            path, json={"email": email, **fields}, headers={"X-Real-IP": ip}
        )


# resend ---------------------------------------------------------------------


async def test_resend_answers_the_same_whether_or_not_the_address_is_a_customer(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """Anything else would let the route tell a stranger who has bought."""
    keygen_store.add("lic-buyer", email="buyer@example.com")

    found = await post("/license/resend", "buyer@example.com")
    missing = await post("/license/resend", "stranger@example.com")

    assert (found.status_code, missing.status_code) == (200, 200)
    assert found.json() == missing.json()
    assert mailer.sent == [("resend", "buyer@example.com", ["CERT-lic-buyer"])]


async def test_resend_mails_nothing_for_a_suspended_license_and_says_the_same(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """A refunded license is suspended; mailing it back would undo the refund."""
    keygen_store.add("lic-refunded", status="SUSPENDED", email="refunded@example.com")

    suspended = await post("/license/resend", "refunded@example.com")
    missing = await post("/license/resend", "stranger@example.com")

    assert suspended.status_code == 200
    assert suspended.json() == missing.json()
    assert mailer.sent == []


async def test_resend_answers_the_same_when_the_mail_server_refuses_the_address(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """A refusal would confirm the address belongs to a customer."""
    keygen_store.add("lic-buyer", email="buyer@example.com")
    mailer.error = MailerRejectedError("550 no such user")

    refused = await post("/license/resend", "buyer@example.com")
    missing = await post("/license/resend", "stranger@example.com")

    assert refused.status_code == 200
    assert refused.json() == missing.json()


async def test_resend_is_503_when_mail_is_off_before_any_lookup(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """Checked first, so the refusal says nothing about the address."""
    mailer.enabled = False

    reply = await post("/license/resend", "buyer@example.com")

    assert reply.status_code == 503
    assert keygen_store.requests == []


async def test_resend_is_503_when_keygen_is_down(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    keygen_store.down = True

    reply = await post("/license/resend", "buyer@example.com")

    assert reply.status_code == 503


async def test_resend_is_503_when_the_mailer_is_down(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    keygen_store.add("lic-buyer", email="buyer@example.com")
    mailer.error = MailerUnavailableError("timed out")

    reply = await post("/license/resend", "buyer@example.com")

    assert reply.status_code == 503


# trial ----------------------------------------------------------------------


async def test_trial_is_404_when_trials_are_off(
    mailer: Mailer, keygen_store: FakeKeygen, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "LICENSE_TRIAL_ENABLED", False)

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 404


async def test_trial_is_400_for_a_disposable_address_before_keygen(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """One trial per inbox means nothing for an inbox anyone can open."""
    reply = await post("/license/trial", "new@mailinator.com")

    assert reply.status_code == 400
    assert keygen_store.requests == []
    assert mailer.sent == []


async def test_a_tagged_address_cannot_claim_a_second_trial(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """Folded, new+a@ and new+b@ are one person: plus-tagging is the cheapest farm."""
    first = await post("/license/trial", "new+a@example.com")
    second = await post("/license/trial", "new+b@example.com")

    assert (first.status_code, second.status_code) == (200, 409)
    assert len(keygen_store.licenses) == 1
    assert [to for _, to, _ in mailer.sent] == ["new+a@example.com"]


async def test_trial_is_503_when_keygen_is_down_and_points_at_resend(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """Resend finds a trial created before the failure."""
    keygen_store.down = True

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 503
    assert "resend" in reply.json()["detail"]


async def test_trial_is_400_when_the_mail_server_refuses_the_address(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """The caller typed the address, so a refusal is theirs to correct."""
    mailer.error = MailerRejectedError("550 no such user")

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 400
    assert "refused" in reply.json()["detail"]


async def test_trial_is_503_when_mail_is_down_and_says_the_trial_exists(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """The address is spent, so the caller is told where the file is."""
    mailer.error = MailerUnavailableError("timed out")

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 503
    assert "created" in reply.json()["detail"]
    assert len(keygen_store.licenses) == 1


async def test_trial_mails_the_file_and_never_returns_it(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """Delivery to a real inbox is what makes one trial per address mean anything."""
    reply = await post("/license/trial", "new@example.com")

    (license_id,) = keygen_store.licenses
    assert reply.status_code == 200
    assert f"CERT-{license_id}" not in reply.text
    assert mailer.sent == [("trial", "new@example.com", [f"CERT-{license_id}"])]


# trial funnel event ---------------------------------------------------------


async def test_an_issued_trial_is_counted_by_channel_and_nothing_else(
    mailer: Mailer, keygen_store: FakeKeygen, posthog_events
) -> None:
    reply = await post("/license/trial", "new@example.com", channel="hn")

    (license_id,) = keygen_store.licenses
    (event,) = posthog_events.named("license_trial_issued")
    assert reply.status_code == 200
    assert event["properties"] == {
        "source": "backend",
        "channel": "hn",
        "$process_person_profile": False,
    }
    assert "new@example.com" not in repr(event)
    assert license_id not in repr(event)


async def test_a_bad_channel_is_dropped_and_never_costs_the_trial(
    mailer: Mailer, keygen_store: FakeKeygen, posthog_events
) -> None:
    reply = await post("/license/trial", "new@example.com", channel="Not A Tag!")

    (event,) = posthog_events.named("license_trial_issued")
    assert reply.status_code == 200
    assert event["properties"]["channel"] == "unknown"


async def test_an_old_page_without_a_channel_still_gets_its_trial(
    mailer: Mailer, keygen_store: FakeKeygen, posthog_events
) -> None:
    reply = await post("/license/trial", "new@example.com")

    (event,) = posthog_events.named("license_trial_issued")
    assert reply.status_code == 200
    assert event["properties"]["channel"] == "unknown"


async def test_a_trial_that_was_not_issued_is_not_counted(
    mailer: Mailer, keygen_store: FakeKeygen, posthog_events
) -> None:
    first = await post("/license/trial", "taken@example.com", channel="hn")
    again = await post("/license/trial", "taken@example.com", channel="hn")
    disposable = await post("/license/trial", "x@33mail.com", channel="hn")

    assert (first.status_code, again.status_code, disposable.status_code) == (
        200,
        409,
        400,
    )
    assert len(posthog_events.named("license_trial_issued")) == 1


async def test_a_trial_whose_mail_failed_is_still_counted_as_issued(
    mailer: Mailer, keygen_store: FakeKeygen, posthog_events
) -> None:
    """The address is spent either way, and resend will deliver it."""
    mailer.error = MailerUnavailableError("timed out")

    reply = await post("/license/trial", "new@example.com", channel="hn")

    assert reply.status_code == 503
    assert len(posthog_events.named("license_trial_issued")) == 1


# file -----------------------------------------------------------------------


async def test_the_success_page_downloads_its_purchase_file(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    keygen_store.add("lic-paid", email="buyer@example.com", checkoutSessionId="cs_paid")

    async with portal() as client:
        reply = await client.get("/license/file", params={"session_id": "cs_paid"})

    assert reply.status_code == 200
    assert reply.text == "CERT-lic-paid"
    assert (
        reply.headers["content-disposition"] == 'attachment; filename="surfsense.lic"'
    )


async def test_an_unknown_checkout_session_has_no_file(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """With no license for it and no Stripe to fulfil from, there is nothing to serve."""
    async with portal() as client:
        reply = await client.get("/license/file", params={"session_id": "cs_unknown"})

    assert reply.status_code == 404


async def test_the_success_page_serves_no_file_for_a_refunded_purchase(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    """A refund suspends the license, and Keygen would still check a file out."""
    keygen_store.add(
        "lic-refunded",
        status="SUSPENDED",
        email="buyer@example.com",
        checkoutSessionId="cs_refunded",
    )

    async with portal() as client:
        reply = await client.get("/license/file", params={"session_id": "cs_refunded"})

    assert reply.status_code == 404
    assert not any(r.url.path.endswith("/check-out") for r in keygen_store.requests)


async def test_every_file_is_checked_out_right_after_its_license_validates(
    mailer: Mailer, keygen_store: FakeKeygen
) -> None:
    keygen_store.add("lic-one", email="buyer@example.com")
    keygen_store.add("lic-two", email="buyer@example.com")

    await post("/license/resend", "buyer@example.com")

    actions = [
        request.url.path.split("/licenses/", 1)[1]
        for request in keygen_store.requests
        if "/actions/" in request.url.path
    ]
    assert actions == [
        "lic-one/actions/validate",
        "lic-one/actions/check-out",
        "lic-two/actions/validate",
        "lic-two/actions/check-out",
    ]


# rate limits ----------------------------------------------------------------


async def test_the_ip_bucket_bites_across_addresses(
    mailer: Mailer, monkeypatch: pytest.MonkeyPatch
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
    mailer: Mailer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Folded, so a +tag is the same address; spread over IPs, still one address."""
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 2)

    codes = [
        (await post("/license/resend", email, ip=f"203.0.113.{n}")).status_code
        for n, email in enumerate(
            ["user@example.com", "user+a@example.com", "user+b@example.com"]
        )
    ]

    assert codes == [200, 200, 429]


async def test_a_limit_of_zero_turns_its_bucket_off(
    mailer: Mailer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 0)

    codes = {
        (await post("/license/resend", "buyer@example.com")).status_code
        for _ in range(20)
    }

    assert codes == {200}
