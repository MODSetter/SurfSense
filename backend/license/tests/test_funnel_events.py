"""Funnel counts from the licence server: personless, channel-only, once each.

Asserted from the PostHog client's side, so what is checked is exactly what
would leave the server.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from license import issue, keygen
from license.funnel.channel import channel_from_reference, valid_channel
from license.issue import derive_license_id, fulfill_license_session
from license.models import IssuedLicense

pytestmark = pytest.mark.unit

PERSONAL = ("buyer@example.com", "cus_1", "cs_paid")


def _paid_session(**overrides) -> SimpleNamespace:
    fields = {
        "id": "cs_paid",
        "mode": "payment",
        "payment_status": "paid",
        "metadata": {"purchase_type": "license", "plan": "individual"},
        "customer": "cus_1",
        "customer_details": SimpleNamespace(email="buyer@example.com"),
        "amount_total": 6000,
        "currency": "USD",
        "client_reference_id": "hn",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.fixture
def keygen_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, IssuedLicense]:
    """Keygen's create refuses a second license under the same derived id."""
    store: dict[str, IssuedLicense] = {}

    async def create_license(plan, email, max_users=None, *, license_id=None, **_):
        if license_id in store:
            raise keygen.LicenseExistsError(license_id)
        store[license_id] = IssuedLicense(
            keygen_license_id=license_id,
            certificate=f"CERT-{license_id}",
            plan=plan,
            email=email,
        )
        return license_id

    async def checkout_license(license_id):
        return store[license_id].certificate

    async def issued_for_id(license_id):
        return store.get(license_id)

    monkeypatch.setattr(keygen, "create_license", create_license)
    monkeypatch.setattr(keygen, "checkout_license", checkout_license)
    monkeypatch.setattr(issue, "issued_for_id", issued_for_id)
    return store


# channel tags -----------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["hn", "direct", "news-ycombinator-com", "a_b", "x" * 40]
)
def test_a_channel_tag_is_kept_as_sent(value):
    assert valid_channel(value) == value


@pytest.mark.parametrize(
    "value", [None, "", "HN", "x" * 41, "a b", "you@example.com", "ref:hn", 7]
)
def test_anything_else_is_not_a_channel(value):
    assert valid_channel(value) is None


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("hn", "hn"),
        ("Hacker_News", "hacker_news"),
        ("--weird value!!", "weird-value"),
        ("x" * 200, "x" * 40),
        ("", None),
        ("!!!", None),
        (None, None),
    ],
)
def test_a_client_reference_id_is_reduced_to_a_tag(reference, expected):
    """Anyone can edit a Payment Link's query string, so it is reduced, not trusted."""
    assert channel_from_reference(reference) == expected


# license_purchased --------------------------------------------------------------


async def test_a_new_purchase_is_counted_with_plan_amount_and_channel(
    keygen_store, posthog_events
):
    await fulfill_license_session(_paid_session())

    (event,) = posthog_events.named("license_purchased")
    assert event["properties"] == {
        "source": "backend",
        "plan": "individual",
        "amount_total": 6000,
        "currency": "usd",
        "channel": "hn",
        "$process_person_profile": False,
    }
    assert event["disable_geoip"] is True


async def test_the_purchase_event_names_no_buyer_licence_or_session(
    keygen_store, posthog_events
):
    await fulfill_license_session(_paid_session())

    (event,) = posthog_events.named("license_purchased")
    license_id = derive_license_id("stripe", "cs_paid")
    flattened = repr(event)
    for value in (*PERSONAL, license_id):
        assert value not in flattened


async def test_the_webhook_and_the_success_page_count_one_purchase(
    keygen_store, posthog_events
):
    """Both fulfil the same payment; only the one that minted the licence counts it."""
    first = await fulfill_license_session(_paid_session())
    second = await fulfill_license_session(_paid_session())

    assert first.keygen_license_id == second.keygen_license_id
    assert len(posthog_events.named("license_purchased")) == 1


async def test_a_checkout_without_a_reference_is_counted_as_unknown(
    keygen_store, posthog_events
):
    await fulfill_license_session(_paid_session(client_reference_id=None))

    (event,) = posthog_events.named("license_purchased")
    assert event["properties"]["channel"] == "unknown"


async def test_each_purchase_gets_its_own_distinct_id(keygen_store, posthog_events):
    await fulfill_license_session(_paid_session(id="cs_one"))
    await fulfill_license_session(_paid_session(id="cs_two"))

    ids = {event["distinct_id"] for event in posthog_events.named("license_purchased")}
    assert len(ids) == 2


async def test_purchases_still_issue_with_analytics_off(keygen_store, monkeypatch):
    """No POSTHOG_API_KEY is the default for self-hosters."""
    from license import analytics

    monkeypatch.setattr(analytics, "_client", None)
    monkeypatch.setattr(analytics, "_init_attempted", True)

    issued = await fulfill_license_session(_paid_session())

    assert issued.certificate.startswith("CERT-")
