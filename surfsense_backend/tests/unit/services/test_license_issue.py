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
from app.services import keygen, license_service
from app.services.license_email import fold_email, is_disposable, normalize_email
from app.services.license_service import (
    LicenseIssueError,
    LicenseNotFoundError,
    TrialAlreadyClaimedError,
    _trial_expiry,
    certificates_for_email,
    correct_license_email,
    find_license_by_checkout_session,
    fulfill_license_session,
    issue_license,
    issue_trial_license,
    resolve_license_plan,
    suspend_licenses_for_customer,
)
from tests.utils.fake_keygen import FakeKeygen

pytestmark = pytest.mark.unit


@pytest.fixture
def keygen_config(monkeypatch):
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    monkeypatch.setattr(config, "KEYGEN_POLICY_INDIVIDUAL", "policy-individual")
    monkeypatch.setattr(config, "KEYGEN_POLICY_TEAM", "policy-team")
    return config


@pytest.fixture
def fake_keygen(monkeypatch, keygen_config):
    return FakeKeygen().install(monkeypatch, license_service.keygen)


@pytest.fixture(autouse=True)
def _no_redis_locks(monkeypatch):
    """Locks narrow a race; they are not the correctness check under test."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop(_key, **_kwargs):
        yield True

    monkeypatch.setattr(license_service, "license_lock", _noop)


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


# -- Keygen request shapes --------------------------------------------------


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


# -- Issuing ---------------------------------------------------------------


async def test_issue_license_normalizes_the_email_and_returns_the_certificate(
    fake_keygen,
):
    issued = await issue_license(
        plan="individual", email="  Buyer@Example.COM ", source="stripe"
    )

    assert issued.email == "buyer@example.com"
    assert issued.certificate.startswith("-----BEGIN LICENSE FILE-----")
    stored = fake_keygen.licenses[issued.keygen_license_id]["attributes"]["metadata"]
    assert stored["email"] == "buyer@example.com"


async def test_seats_are_dropped_for_non_team_plans(fake_keygen):
    issued = await issue_license(
        plan="individual", email="a@b.test", max_users=9, source="stripe"
    )

    assert issued.max_users is None


# -- Trial expiry ----------------------------------------------------------


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


# -- Trial dedupe (the replacement for the deleted ledger table) -----------


async def test_a_second_trial_for_the_same_address_is_refused(fake_keygen):
    await issue_trial_license("buyer@example.com")

    with pytest.raises(TrialAlreadyClaimedError):
        await issue_trial_license("buyer@example.com")


async def test_plus_tagging_cannot_farm_extra_trials(fake_keygen):
    """Plus-tagging is the cheapest trial farm, so dedupe folds it."""
    await issue_trial_license("buyer@example.com")

    with pytest.raises(TrialAlreadyClaimedError):
        await issue_trial_license("buyer+two@example.com")


async def test_a_trial_indexes_delivery_and_dedupe_separately(fake_keygen):
    """Mail must reach the tagged address; dedupe must still fold it."""
    await issue_trial_license("Buyer+tag@Example.com")

    stored = next(iter(fake_keygen.licenses.values()))["attributes"]["metadata"]
    assert stored["email"] == "buyer+tag@example.com"
    assert stored["trialKey"] == "buyer@example.com"


async def test_a_tagged_address_cannot_reclaim_its_own_trial(fake_keygen):
    """Regression: folding only on lookup let the first tagged claim repeat."""
    await issue_trial_license("buyer+tag@example.com")

    with pytest.raises(TrialAlreadyClaimedError):
        await issue_trial_license("buyer+other@example.com")
    with pytest.raises(TrialAlreadyClaimedError):
        await issue_trial_license("buyer@example.com")


async def test_a_different_address_still_gets_its_own_trial(fake_keygen):
    await issue_trial_license("one@example.com")
    await issue_trial_license("two@example.com")

    assert len(fake_keygen.licenses) == 2


# -- Email rules -----------------------------------------------------------


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


# -- Plan resolution -------------------------------------------------------


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


def test_line_items_are_fetched_once_per_session(monkeypatch):
    """The webhook classifies then fulfils; a Payment Link must not pay twice."""
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_INDIVIDUAL", "price_ind")
    monkeypatch.setattr(config, "STRIPE_PRICE_LICENSE_TEAM", "")

    calls = []

    class _Stripe:
        def __init__(self):
            self.v1 = SimpleNamespace(
                checkout=SimpleNamespace(
                    sessions=SimpleNamespace(retrieve=self._retrieve)
                )
            )

        def _retrieve(self, session_id, params=None):
            calls.append(session_id)
            return SimpleNamespace(
                line_items=SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            price=SimpleNamespace(id="price_ind"), quantity=1
                        )
                    ]
                )
            )

    session = _session()
    stripe = _Stripe()

    assert resolve_license_plan(session, stripe_client=stripe) == ("individual", None)
    assert resolve_license_plan(session, stripe_client=stripe) == ("individual", None)
    assert calls == ["cs_1"]


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


# -- Fulfilment ------------------------------------------------------------


async def test_fulfilment_is_idempotent_via_the_keygen_lookup(fake_keygen):
    """With no table there is no unique row; the Keygen list is the check."""
    session = _session(metadata={"purchase_type": "license", "plan": "individual"})

    first = await fulfill_license_session(session)
    second = await fulfill_license_session(session)

    assert first.keygen_license_id == second.keygen_license_id
    assert len(fake_keygen.licenses) == 1


async def test_fulfilment_records_the_lookup_keys_on_the_license(fake_keygen):
    issued = await fulfill_license_session(
        _session(metadata={"purchase_type": "license", "plan": "individual"})
    )

    stored = fake_keygen.licenses[issued.keygen_license_id]["attributes"]["metadata"]
    assert stored["checkoutSessionId"] == "cs_1"
    assert stored["stripeCustomerId"] == "cus_1"


async def test_an_unpaid_session_is_never_fulfilled(fake_keygen):
    with pytest.raises(LicenseIssueError, match="not paid"):
        await fulfill_license_session(
            _session(
                metadata={"purchase_type": "license", "plan": "individual"},
                payment_status="unpaid",
            )
        )


async def test_a_session_without_an_email_cannot_produce_a_license(fake_keygen):
    """The email is the only identity a license has; there is nothing else."""
    with pytest.raises(LicenseIssueError, match="email"):
        await fulfill_license_session(
            _session(
                metadata={"purchase_type": "license", "plan": "individual"}, email=None
            )
        )


async def test_resending_re_checks_out_every_license_for_that_address(fake_keygen):
    await issue_license(plan="individual", email="buyer@example.com", source="stripe")
    await issue_license(
        plan="team", email="buyer@example.com", max_users=5, source="stripe"
    )

    certificates = await certificates_for_email("Buyer@Example.com")

    assert len(certificates) == 2
    # Fresh checkouts, per contract 1 producer rule 5.
    assert len(fake_keygen.checkouts) == 4


async def test_resending_an_unknown_address_finds_nothing(fake_keygen):
    assert await certificates_for_email("nobody@example.com") == []


async def test_a_refund_suspends_every_license_that_customer_holds(fake_keygen):
    issued = await fulfill_license_session(
        _session(metadata={"purchase_type": "license", "plan": "individual"})
    )

    suspended = await suspend_licenses_for_customer("cus_1")

    assert suspended == 1
    assert fake_keygen.suspended == [issued.keygen_license_id]


# -- Support corrections ---------------------------------------------------


async def test_a_license_is_found_by_its_stripe_payment(fake_keygen):
    """Support matches the payment, not how similar two addresses look."""
    await fulfill_license_session(
        _session(metadata={"purchase_type": "license", "plan": "individual"})
    )

    record = await find_license_by_checkout_session("cs_1")

    assert record.metadata["email"] == "buyer@example.com"
    assert record.keygen_license_id in fake_keygen.licenses


async def test_an_unknown_payment_is_refused(fake_keygen):
    with pytest.raises(LicenseNotFoundError):
        await find_license_by_checkout_session("cs_missing")


async def test_a_duplicated_payment_refuses_to_guess(fake_keygen, monkeypatch):
    """Two licenses for one payment means the idempotency race lost."""

    async def two(*_args, **_kwargs):
        return [{"id": "lic_a", "attributes": {}}, {"id": "lic_b", "attributes": {}}]

    monkeypatch.setattr(license_service.keygen, "list_licenses", two)

    with pytest.raises(LicenseNotFoundError, match="resolve the duplicate"):
        await find_license_by_checkout_session("cs_1")


async def test_correcting_a_typo_rewrites_the_stored_address(fake_keygen):
    """Mailing the file is not enough: resend looks the buyer up by this."""
    await fulfill_license_session(
        _session(
            metadata={"purchase_type": "license", "plan": "individual"},
            email="buyer@gmial.com",
        )
    )
    record = await find_license_by_checkout_session("cs_1")

    issued = await correct_license_email(record, "Buyer@Gmail.com")

    assert issued.email == "buyer@gmail.com"
    stored = fake_keygen.licenses[issued.keygen_license_id]["attributes"]["metadata"]
    assert stored["email"] == "buyer@gmail.com"


async def test_a_corrected_buyer_can_then_self_serve(fake_keygen):
    """The whole point: no more support tickets for this customer."""
    await fulfill_license_session(
        _session(
            metadata={"purchase_type": "license", "plan": "individual"},
            email="buyer@gmial.com",
        )
    )
    record = await find_license_by_checkout_session("cs_1")
    await correct_license_email(record, "buyer@gmail.com")

    assert await certificates_for_email("buyer@gmail.com") != []
    assert await certificates_for_email("buyer@gmial.com") == []


async def test_correcting_preserves_the_payment_and_plan_metadata(fake_keygen):
    """Lose checkoutSessionId and the license is unfindable by payment again."""
    await fulfill_license_session(
        _session(metadata={"purchase_type": "license", "plan": "team", "quantity": "6"})
    )
    record = await find_license_by_checkout_session("cs_1")

    issued = await correct_license_email(record, "ops@acme.com")

    stored = fake_keygen.licenses[issued.keygen_license_id]["attributes"]["metadata"]
    assert stored["checkoutSessionId"] == "cs_1"
    assert stored["stripeCustomerId"] == "cus_1"
    assert stored["plan"] == "team"
    assert issued.max_users == 6


async def test_correcting_a_trial_moves_the_dedupe_key_too(fake_keygen):
    """Otherwise the corrected address could claim a second trial."""
    issued = await issue_trial_license("person@gmial.com")
    record = license_service.LicenseRecord(
        keygen_license_id=issued.keygen_license_id,
        metadata=fake_keygen.licenses[issued.keygen_license_id]["attributes"][
            "metadata"
        ],
    )

    await correct_license_email(record, "person+tag@gmail.com")

    stored = fake_keygen.licenses[issued.keygen_license_id]["attributes"]["metadata"]
    assert stored["email"] == "person+tag@gmail.com"
    assert stored["trialKey"] == "person@gmail.com"
    with pytest.raises(TrialAlreadyClaimedError):
        await issue_trial_license("person@gmail.com")


async def test_an_empty_replacement_address_is_refused(fake_keygen):
    await fulfill_license_session(
        _session(metadata={"purchase_type": "license", "plan": "individual"})
    )
    record = await find_license_by_checkout_session("cs_1")

    with pytest.raises(ValueError, match="required"):
        await correct_license_email(record, "   ")
