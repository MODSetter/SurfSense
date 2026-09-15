"""Issuing licenses with Keygen as the only system of record.

There is no license table, so these tests assert on what reaches Keygen and on
the lookups that replace the unique constraints a table would have given us.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from app.config import config
from app.license import keygen
from app.license.delivery.email import fold_email, is_disposable, normalize_email
from app.license.service import (
    LicenseIssueError,
    _trial_expiry,
    derive_license_id,
    resolve_license_plan,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def keygen_config(monkeypatch):
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    # Cloud unless a test says otherwise, whatever the developer's environment.
    monkeypatch.setattr(config, "KEYGEN_API_URL", "")
    monkeypatch.setattr(config, "KEYGEN_HOST", "")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    monkeypatch.setattr(config, "KEYGEN_POLICY_INDIVIDUAL", "policy-individual")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TEAM", "policy-team")
    return config


def _session(
    *,
    session_id="cs_1",
    metadata=None,
    email="Buyer@Example.com",
    customer="cus_1",
    payment_status="paid",
    line_items=None,
):
    return SimpleNamespace(
        id=session_id,
        mode="payment",
        payment_status=payment_status,
        metadata=metadata if metadata is not None else {},
        customer=customer,
        customer_details=SimpleNamespace(email=email),
        line_items=SimpleNamespace(data=line_items) if line_items else None,
    )


async def test_create_and_checkout_send_the_shapes_the_contract_requires(
    keygen_config,
):
    """Contract 1: metadata carries the lookup keys, and checkout uses ttl=null."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/check-out"):
            return httpx.Response(
                200, json={"data": {"attributes": {"certificate": "CERT"}}}
            )
        return httpx.Response(201, json={"data": {"id": "lic_1"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        license_id = await keygen.create_license(
            "team",
            "buyer@example.com",
            12,
            extra_metadata={"checkoutSessionId": "cs_1", "stripeCustomerId": "cus_1"},
            client=client,
        )
        certificate = await keygen.checkout_license(license_id, client=client)

    created = json.loads(requests[0].read())["data"]
    assert created["attributes"]["maxUsers"] == 12
    assert created["attributes"]["metadata"] == {
        "plan": "team",
        "email": "buyer@example.com",
        "checkoutSessionId": "cs_1",
        "stripeCustomerId": "cus_1",
    }
    assert created["relationships"]["policy"]["data"]["id"] == "policy-team"
    # The 30-day default TTL would kill every license a month after purchase.
    assert json.loads(requests[1].read()) == {"meta": {"ttl": None}}
    assert certificate == "CERT"


async def test_list_filters_use_keygen_metadata_query_syntax(keygen_config):
    """A wrong filter key returns [] rather than an error, so the shape matters."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await keygen.list_licenses(
            metadata={"checkoutSessionId": "cs_1"}, policy="policy-trial", client=client
        )

    query = str(seen[0].url)
    assert "metadata%5BcheckoutSessionId%5D=cs_1" in query
    assert "policy=policy-trial" in query


async def test_team_license_requires_seats(keygen_config):
    with pytest.raises(ValueError, match="max_users"):
        await keygen.create_license("team", "a@b.test", None)


async def _captured_get(client_kwargs=None) -> httpx.Request:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await keygen.get_license("lic_1", client=client)
    return seen[0]


async def test_unconfigured_calls_go_to_keygen_cloud(keygen_config):
    request = await _captured_get()

    assert str(request.url) == "https://api.keygen.sh/v1/accounts/acct/licenses/lic_1"
    assert "X-Forwarded-Proto" not in request.headers


async def test_a_self_hosted_call_carries_the_host_the_account_is_keyed_on(
    keygen_config, monkeypatch
):
    """CE reads the account from Host, so the alias we dial is not the name it knows."""
    monkeypatch.setattr(config, "KEYGEN_API_URL", "http://keygen-web:3000/v1/accounts/")
    monkeypatch.setattr(config, "KEYGEN_HOST", "keygen.internal")

    request = await _captured_get()

    assert str(request.url) == "http://keygen-web:3000/v1/accounts/acct/licenses/lic_1"
    assert request.headers["Host"] == "keygen.internal"
    # Absent this, CE 308s the call and the redirect reads as "no such license".
    assert request.headers["X-Forwarded-Proto"] == "https"


def test_trial_expiry_is_measured_from_now_once_the_plugin_has_shipped(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_TRIAL_EXPIRY_FLOOR", "")
    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)

    now = datetime.now(UTC)
    assert abs(_trial_expiry(now) - (now + timedelta(days=14))) < timedelta(seconds=1)


def test_trial_expiry_starts_at_the_plugin_date_while_it_is_in_the_future(monkeypatch):
    """The gap week between launch and the plugin must not eat the trial."""
    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)
    now = datetime(2026, 9, 14, tzinfo=UTC)
    monkeypatch.setattr(config, "LICENSE_TRIAL_EXPIRY_FLOOR", "2026-09-21")

    assert _trial_expiry(now) == datetime(2026, 10, 5, tzinfo=UTC)


def test_an_unparseable_expiry_floor_degrades_to_plain_days(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)
    monkeypatch.setattr(config, "LICENSE_TRIAL_EXPIRY_FLOOR", "next tuesday")

    now = datetime.now(UTC)
    assert abs(_trial_expiry(now) - (now + timedelta(days=14))) < timedelta(seconds=1)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Buyer@Example.COM ", "buyer@example.com"),
        ("buyer+surfsense@example.com", "buyer+surfsense@example.com"),
    ],
)
def test_delivery_uses_the_address_as_typed(raw, expected):
    """`user+tag@` is deliverable and may be deliberate, so delivery keeps it."""
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("buyer+tag@example.com", "buyer@example.com"),
        ("buyer@example.com", "buyer@example.com"),
        # Dot-folding is Gmail-specific; applying it everywhere would collide
        # distinct addresses at other providers.
        ("b.uyer@example.com", "b.uyer@example.com"),
    ],
)
def test_dedupe_folds_plus_tags_but_not_dots(raw, expected):
    assert fold_email(raw) == expected


def test_disposable_domains_are_recognised(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_DISPOSABLE_EMAIL_DOMAINS", "burner.test")

    assert is_disposable("a@mailinator.com") is True
    assert is_disposable("a@burner.test") is True
    assert is_disposable("a@surfsense.net") is False


def test_plan_comes_from_session_metadata_when_present():
    resolved = resolve_license_plan(
        _session(metadata={"purchase_type": "license", "plan": "team", "quantity": "7"})
    )

    assert resolved == ("team", 7)


def test_plan_falls_back_to_the_price_id_for_payment_links(monkeypatch):
    """Payment Links carry no session metadata, so the price is the only signal."""
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_INDIVIDUAL", "price_ind")
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_TEAM", "price_team")

    session = _session(
        line_items=[SimpleNamespace(price=SimpleNamespace(id="price_team"), quantity=9)]
    )

    assert resolve_license_plan(session) == ("team", 9)


def test_an_unrelated_checkout_is_not_a_license(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_INDIVIDUAL", "price_ind")
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_TEAM", "")

    session = _session(
        line_items=[
            SimpleNamespace(price=SimpleNamespace(id="price_socks"), quantity=1)
        ]
    )

    assert resolve_license_plan(session) is None


def test_no_configured_prices_means_no_price_lookup(monkeypatch):
    """Ordinary checkouts must not pay for an extra Stripe call."""
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_INDIVIDUAL", "")
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_TEAM", "")

    assert resolve_license_plan(_session()) is None


def test_a_bad_plan_in_metadata_is_an_error():
    with pytest.raises(LicenseIssueError, match="Unsupported license plan"):
        resolve_license_plan(
            _session(metadata={"purchase_type": "license", "plan": "platinum"})
        )


def test_a_team_purchase_without_a_quantity_is_an_error():
    with pytest.raises(LicenseIssueError, match="quantity"):
        resolve_license_plan(
            _session(metadata={"purchase_type": "license", "plan": "team"})
        )


def test_the_derived_id_is_stable_and_scoped():
    """Same purchase, same id; a trial and a purchase never collide."""
    assert derive_license_id("stripe", "cs_1") == derive_license_id("stripe", "cs_1")
    assert derive_license_id("stripe", "cs_1") != derive_license_id("trial", "cs_1")
    assert derive_license_id("stripe", "cs_1") != derive_license_id("stripe", "cs_2")


def _conflict_handler(lookup_status: int, lookups: list[httpx.Request]):
    """A create that 409s, and a lookup answering ``lookup_status``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            lookups.append(request)
            return httpx.Response(lookup_status, json={"data": {"id": "lic-1"}})
        return httpx.Response(409, json={"errors": [{"title": "Conflict"}]})

    return handler


async def test_a_committed_duplicate_id_is_reported_as_existing(keygen_config):
    """Validation catches it: 422 with an explicit ID_CONFLICT code."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"errors": [{"code": "ID_CONFLICT"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(keygen.LicenseExistsError):
            await keygen.create_license(
                "individual", "a@b.test", license_id="lic-1", client=client
            )


async def test_a_concurrent_duplicate_id_is_reported_as_existing(keygen_config):
    """The race loses at the unique index instead: a bare 409, no error code.

    This is the shape a real webhook-vs-success-page collision produces, so
    matching only the 422 would miss every race this design exists to settle.
    """
    lookups: list[httpx.Request] = []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_conflict_handler(200, lookups))
    ) as client:
        with pytest.raises(keygen.LicenseExistsError):
            await keygen.create_license(
                "individual", "a@b.test", license_id="lic-1", client=client
            )

    assert lookups, "a 409 carries no code, so the id must be confirmed"


async def test_an_unrelated_conflict_is_not_mistaken_for_an_existing_license(
    keygen_config,
):
    """Otherwise any 409 would tell a first-time claimant their trial is used."""
    lookups: list[httpx.Request] = []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_conflict_handler(404, lookups))
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await keygen.create_license(
                "individual", "a@b.test", license_id="lic-1", client=client
            )
