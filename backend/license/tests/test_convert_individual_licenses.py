"""`python -m license.scripts.convert_individual_licenses`: each Individual license sold becomes Business Solo.

Keygen and Stripe are faked at their transports and the mail is built for real
and caught at the mailer (`tests/billing_harness.py`), so the script, its steps
and the notice run as written, and so do the webhook's handlers after it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from license import jobs
from license.email import deliver
from license.email.message import BusinessCopy
from license.job_packs.verdict import LicenseVerdict, license_verdict
from license.records import licenses_for_email
from license.scripts import convert_individual_licenses as script
from license.settings import config
from license.tests.billing_harness import (
    INDIVIDUAL_PRICE,
    PORTAL,
    Billing,
    billing,
    post_event,
)
from license.tests.stripe_fake import event, invoice, subscription
from mailer import MailerUnavailableError

pytestmark = pytest.mark.unit

NOW = datetime.now(UTC).replace(microsecond=0)
TODAY = NOW.date().isoformat()
GRACE = timedelta(days=30)
# A year still running, sold before 3 Nov 2026: the Individual policy's duration
# made the license end when its period does.
PERIOD_END = NOW + timedelta(days=270)
EXPIRY = PERIOD_END.isoformat()
# What the same year buys a Business license: 30 days past the period.
BUSINESS_EXPIRY = PERIOD_END + GRACE
CREATED = "2026-10-30T09:15:00+00:00"
RENEWS = "it renews automatically on"
SCRIPT = "python -m license.scripts.convert_individual_licenses"
POLICY = {
    "scheme": "ED25519_SIGN",
    "encrypted": False,
    "usePool": False,
    "machineUniquenessStrategy": "UNIQUE_PER_LICENSE",
    "componentUniquenessStrategy": "UNIQUE_PER_MACHINE",
    "transferStrategy": "KEEP_EXPIRY",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Billing:
    env = billing(monkeypatch)
    monkeypatch.setattr(script, "get_stripe_client", env.stripe.client)
    monkeypatch.setattr(script, "is_mail_enabled", lambda: True)
    monkeypatch.setattr(script, "get_mailer", lambda: env.mail)
    env.keygen.policies.update(
        {
            "policy-individual": {**POLICY, "name": "Individual", "metadata": {}},
            "policy-business": {
                **POLICY,
                "name": "Business",
                "metadata": {"surfsensePolicy": "business"},
            },
            "policy-business-trial": {
                **POLICY,
                "name": "Business trial",
                "metadata": {"surfsensePolicy": "business-trial"},
            },
        }
    )
    return env


def individual_buyer(
    env: Billing,
    license_id: str = "lic-solo",
    *,
    email: str = "solo@example.com",
    status: str = "ACTIVE",
    expiry: str | None = EXPIRY,
    created: str = CREATED,
    subscription_status: str = "active",
    **metadata: str,
) -> None:
    """Sold through the Individual Payment Link before stripeSubscriptionId was written.

    Its first year was paid by one invoice and one charge, as Stripe holds them.
    """
    session_id, subscription_id = f"cs_{license_id}", f"sub_{license_id}"
    env.keygen.add(
        license_id,
        status,
        policy="policy-individual",
        expiry=expiry,
        created=created,
        plan="individual",
        email=email,
        checkoutSessionId=session_id,
        stripeCustomerId=f"cus_{license_id}",
        **metadata,
    )
    env.stripe.sessions[session_id] = {
        "id": session_id,
        "object": "checkout.session",
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "subscription": subscription_id,
    }
    paid = subscription(
        subscription_id,
        period_end=int(PERIOD_END.timestamp()),
        price=INDIVIDUAL_PRICE,
    )
    paid["status"] = subscription_status
    env.stripe.subscriptions[subscription_id] = paid
    first_year = f"in_{license_id}"
    env.stripe.invoices[first_year] = invoice(
        first_year, subscription_id, reason="subscription_create"
    )
    env.stripe.invoice_paid_by[f"pi_{license_id}"] = first_year
    env.stripe.charges[f"ch_{license_id}"] = {
        "id": f"ch_{license_id}",
        "object": "charge",
        "payment_intent": f"pi_{license_id}",
        "status": "succeeded",
        "amount": 6000,
        "amount_refunded": 0,
        "refunded": False,
        "disputed": False,
    }


def paid_once(env: Billing, license_id: str = "lic-solo") -> None:
    """Its checkout was a one-time payment: no subscription renews it."""
    env.stripe.sessions[f"cs_{license_id}"].update(
        mode="payment", subscription=None, payment_intent=f"pi_{license_id}"
    )
    del env.stripe.subscriptions[f"sub_{license_id}"]
    del env.stripe.invoices[f"in_{license_id}"]
    del env.stripe.invoice_paid_by[f"pi_{license_id}"]


def charge_of(env: Billing, license_id: str = "lic-solo") -> dict:
    return env.stripe.charges[f"ch_{license_id}"]


def stripe_subscription(env: Billing, license_id: str = "lic-solo") -> dict:
    return env.stripe.subscriptions[f"sub_{license_id}"]


def others(env: Billing) -> None:
    """A trial and a Business license, which no run may touch."""
    env.keygen.add(
        "lic-trial",
        policy="policy-trial",
        expiry=EXPIRY,
        plan="trial",
        email="trial@example.com",
        trialKey="trial@example.com",
    )
    env.keygen.add(
        "lic-firm",
        policy="policy-business",
        expiry=EXPIRY,
        max_users=3,
        plan="business",
        email="partner@acme.example",
        jobs="JOB_QUESTIONNAIRE",
        stripeSubscriptionId="sub_firm",
    )


def held(env: Billing, license_id: str = "lic-solo") -> dict:
    return env.keygen.licenses[license_id]


def expiry_of(env: Billing, license_id: str = "lic-solo") -> datetime | None:
    expiry = held(env, license_id)["attributes"]["expiry"]
    return datetime.fromisoformat(expiry) if expiry else None


def ends_on(moment: datetime) -> str:
    return f"It ends on {moment.day} {moment:%B %Y} and does not renew."


def renews_on(moment: datetime) -> str:
    return (
        f"Your purchase is a yearly subscription: it renews automatically on "
        f"{moment.day} {moment:%B %Y}, and every year after, at the price you paid"
    )


async def run(*argv: str) -> int:
    return await script.main(list(argv))


class MailDown:
    async def send(self, message) -> None:
        raise MailerUnavailableError("timed out")


def failing_notice_marks(
    env: Billing,
    monkeypatch: pytest.MonkeyPatch,
    times: int,
    refusal: Callable[[], httpx2.Response] = lambda: httpx2.Response(503),
):
    """Keygen answers `refusal` to the first `times` writes of the notice's mark."""
    answer = env.keygen.handle
    refused: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.method == "PATCH" and len(refused) < times:
            metadata = json.loads(request.content)["data"]["attributes"].get("metadata")
            if "conversionNoticeSentOn" in (metadata or {}):
                refused.append(request)
                env.keygen.requests.append(request)
                return refusal()
        return answer(request)

    monkeypatch.setattr(env.keygen, "handle", handle)
    return refused


# the dry run --------------------------------------------------------------------


async def test_a_dry_run_lists_only_the_licenses_it_would_convert_and_changes_nothing(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    individual_buyer(
        env, "lic-refunded", email="refunded@example.com", status="SUSPENDED"
    )
    individual_buyer(
        env,
        "lic-lapsed",
        email="lapsed@example.com",
        expiry="2026-10-01T00:00:00+00:00",
    )
    individual_buyer(
        env, "lic-owing", email="owing@example.com", subscription_status="past_due"
    )
    # Issued by hand before launch: on the policy, but no sale.
    env.keygen.add(
        "lic-internal",
        policy="policy-individual",
        expiry=EXPIRY,
        created=CREATED,
        plan="individual",
        email="founder@example.com",
    )
    # A 30-day trial put on the Individual policy by hand: trials stay as they are.
    env.keygen.add(
        "lic-long-trial",
        policy="policy-individual",
        expiry=EXPIRY,
        created=CREATED,
        plan="trial",
        email="partner@example.com",
        checkoutSessionId="cs_unused",
    )
    others(env)

    assert await run() == 0

    out = capsys.readouterr().out
    assert {request.method for request in env.keygen.requests} == {"GET"}
    assert {method for method, _ in env.stripe.calls} == {"GET"}
    assert env.mail == []
    assert out.startswith(
        "to       policy-business  Business, which keeps each license's expiry "
        "when it moves (KEEP_EXPIRY)\n"
    )
    assert [line for line in out.splitlines() if line.startswith("convert")] == [
        f"convert  lic-solo  s***@example.com  created 2026-10-30  "
        f"expires {PERIOD_END.date()} ({BUSINESS_EXPIRY.date()} once converted)  "
        f"subscription sub_lic-solo, renews on {PERIOD_END.date()}"
    ]
    for line in (
        "skip     lic-refunded  r***@example.com  suspended (a refund, a dispute, or "
        "by hand)",
        "skip     lic-lapsed  l***@example.com  expired on 2026-10-01",
        "skip     lic-owing  o***@example.com  subscription sub_lic-owing is past_due, "
        "neither renewing nor ended; run again once Stripe settles it",
        "skip     lic-internal  f***@example.com  no Stripe purchase on it (issued by "
        "hand or invoiced)",
        "skip     lic-long-trial  p***@example.com  its plan is trial, not individual",
    ):
        assert line in out
    assert "lic-trial" not in out
    assert "lic-firm" not in out
    assert "solo@example.com" not in out
    assert "1 license to convert, 5 skipped, 0 failed" in out


async def test_a_license_whose_checkout_this_stripe_never_held_is_skipped(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """A test-mode purchase, say: the live account answers that it has no such session."""
    individual_buyer(env)
    del env.stripe.sessions["cs_lic-solo"]

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  its checkout session cs_lic-solo is "
        "not in this Stripe account" in capsys.readouterr().out
    )
    assert {request.method for request in env.keygen.requests} == {"GET"}
    assert env.mail == []


async def test_a_checkout_that_was_never_paid_is_not_a_purchase(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Stripe sets a session's subscription only once it completes, so an abandoned
    one reads like a payment made once unless its state is read."""
    individual_buyer(env)
    env.stripe.sessions["cs_lic-solo"].update(
        status="expired", payment_status="unpaid", subscription=None
    )
    del env.stripe.subscriptions["sub_lic-solo"]

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  its checkout session cs_lic-solo "
        "(subscription mode) is expired, unpaid: not a purchase"
        in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_license_whose_subscription_this_stripe_never_held_is_skipped(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """The Keygen contract test leaves licenses with a made-up stripeSubscriptionId."""
    individual_buyer(env, stripeSubscriptionId="sub_contract_x")

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  its subscription sub_contract_x is not "
        "in this Stripe account" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


@pytest.mark.parametrize(
    "given_back",
    [
        {"refunded": True, "amount_refunded": 6000},
        {"amount_refunded": 6000},
        {"disputed": True},
    ],
    ids=["refunded", "refunded-in-parts", "disputed"],
)
async def test_a_buyer_given_their_money_back_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture, given_back: dict
) -> None:
    """The server before the switch release traced no subscription refund and no
    dispute, so such a license may still be active (ADR 0080)."""
    individual_buyer(env)
    charge_of(env).update(given_back)

    assert await run("--apply", "--yes") == 0

    assert (
        f"skip     lic-solo  s***@example.com  subscription sub_lic-solo, renews on "
        f"{PERIOD_END.date()}, yet a payment for it was refunded in full or disputed "
        "and the license is not suspended: a support case" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_partial_refund_keeps_the_purchase(env: Billing) -> None:
    """As the webhook reads one: goodwill, not the purchase given back."""
    individual_buyer(env)
    charge_of(env)["amount_refunded"] = 1000

    assert await run("--apply", "--yes") == 0

    assert held(env)["policy"] == "policy-business"
    assert len(env.mail) == 1


async def test_a_payment_made_once_and_refunded_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    paid_once(env)
    charge_of(env).update(refunded=True, amount_refunded=6000)

    assert await run("--apply", "--yes") == 0

    assert (
        "paid once, with no subscription, so it does not renew, yet a payment for it "
        "was refunded in full or disputed" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_cancel_date_after_another_renewal_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Stripe renews into the period holding the date, prorated, so it neither renews
    every year nor ends with its period (Stripe's cancellation guide)."""
    individual_buyer(env)
    cancel_on = PERIOD_END + timedelta(days=200)
    stripe_subscription(env)["cancel_at"] = int(cancel_on.timestamp())

    assert await run("--apply", "--yes") == 0

    assert (
        f"skip     lic-solo  s***@example.com  subscription sub_lic-solo is set to "
        f"cancel on {cancel_on.date()}, after it renews once more, prorated: a "
        "support case" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_subscription_for_more_than_one_person_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Business Solo is one person; the notice would say so of a purchase for two."""
    individual_buyer(env)
    stripe_subscription(env)["items"]["data"][0]["quantity"] = 2

    assert await run("--apply", "--yes") == 0

    assert (
        "renews on " + str(PERIOD_END.date()) + ", for 2 people, and Business Solo is "
        "one: a support case" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


@pytest.mark.parametrize(
    ("discounts", "converts"),
    [
        ([], False),
        ([{"id": "di_year", "object": "discount", "end": 1_900_000_000}], False),
        ([{"id": "di_forever", "object": "discount", "end": None}], True),
    ],
    ids=["once-used-up", "repeating", "forever"],
)
async def test_a_discounted_year_converts_only_when_its_discount_lasts(
    env: Billing, capsys: pytest.CaptureFixture, discounts: list, converts: bool
) -> None:
    """The notice's "at the price you paid" holds only when the year paid for renews at
    its discount: a once coupon leaves the subscription after its invoice (Stripe's
    coupons guide), and a repeating one ends."""
    individual_buyer(env)
    env.stripe.invoices["in_lic-solo"]["total_discount_amounts"] = [
        {"amount": 6000, "discount": "di_year"}
    ]
    stripe_subscription(env)["discounts"] = discounts

    assert await run("--apply", "--yes") == 0

    out = capsys.readouterr().out
    left = (
        "yet the year it paid for was discounted and no discount lasts, so it would "
        "not renew at the price paid: a support case"
    )
    if converts:
        assert left not in out
        assert held(env)["policy"] == "policy-business"
        assert len(env.mail) == 1
    else:
        assert left in out
        assert env.keygen.writes("lic-solo") == []
        assert env.mail == []


async def test_a_license_that_never_expires_whose_paid_time_has_passed_is_skipped(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """As Business it would get an expiry already gone, and a notice naming it."""
    ended = NOW - timedelta(days=60)
    individual_buyer(env, expiry=None, subscription_status="canceled")
    stripe_subscription(env)["items"]["data"][0]["current_period_end"] = int(
        ended.timestamp()
    )

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  subscription sub_lic-solo is canceled, "
        "so it does not renew, and the time it paid for ended on "
        f"{(ended + GRACE).date()}" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_license_stripe_cannot_answer_for_fails_and_is_left_alone(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    refused = {
        "error": {"type": "invalid_request_error", "message": "key may not read"}
    }
    monkeypatch.setattr(env.stripe, "_answer", lambda *_: (400, refused))

    assert await run("--apply", "--yes") == 1

    out = capsys.readouterr().out
    assert "failed   lic-solo  s***@example.com  Stripe could not be read: " in out
    assert "key may not read" in out
    assert {request.method for request in env.keygen.requests} == {"GET"}
    assert env.mail == []


async def test_a_license_sold_after_the_decision_converts_only_when_asked(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """ADR 0080 leaves one sold since 1 Nov 2026 to its open question q."""
    individual_buyer(env, created="2026-11-10T12:00:00+00:00")

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  sold on 2026-11-10, after ADR 0080's "
        "decision of 1 Nov 2026, so its open question q decides it; "
        "--include-sold-after-decision converts it" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []

    assert await run("--apply", "--yes", "--include-sold-after-decision") == 0

    assert "(sold after ADR 0080's decision of 1 Nov 2026)" in capsys.readouterr().out
    assert held(env)["policy"] == "policy-business"
    assert len(env.mail) == 1


async def test_two_licenses_on_one_payment_are_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Renewals act on neither, so converting either would be a guess."""
    individual_buyer(env)
    env.keygen.add(
        "lic-dup",
        policy="policy-individual",
        expiry=EXPIRY,
        created="2026-10-30T09:15:01+00:00",
        plan="individual",
        email="solo@example.com",
        checkoutSessionId="cs_lic-solo",
    )

    assert await run("--apply", "--yes") == 0

    out = capsys.readouterr().out
    assert (
        "skip     lic-solo  s***@example.com  shares its payment with lic-dup: "
        "a support case" in out
    )
    assert (
        "skip     lic-dup  s***@example.com  shares its payment with lic-solo: "
        "a support case" in out
    )
    assert env.keygen.writes("lic-solo") == env.keygen.writes("lic-dup") == []
    assert env.mail == []


async def test_a_license_sharing_its_checkout_with_a_suspended_one_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """The likelier duplicate: renewals find two licenses on the session and act on neither."""
    individual_buyer(env)
    env.keygen.add(
        "lic-dup",
        "SUSPENDED",
        policy="policy-individual",
        expiry=EXPIRY,
        created="2026-10-30T09:15:01+00:00",
        plan="individual",
        email="solo@example.com",
        checkoutSessionId="cs_lic-solo",
    )

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  shares its payment with lic-dup: "
        "a support case" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_license_whose_subscription_a_suspended_one_carries_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    env.keygen.add(
        "lic-other",
        "SUSPENDED",
        policy="policy-individual",
        expiry=EXPIRY,
        created="2026-10-30T09:15:01+00:00",
        plan="individual",
        email="solo@example.com",
        checkoutSessionId="cs_other",
        stripeSubscriptionId="sub_lic-solo",
    )

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  shares its payment with lic-other"
        in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_a_license_traced_to_a_subscription_another_carries_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Renewals would find the other by its id and never this one."""
    individual_buyer(env)
    env.keygen.add(
        "lic-other",
        policy="policy-individual",
        expiry=EXPIRY,
        created="2026-10-30T09:15:01+00:00",
        plan="individual",
        email="other@example.com",
        stripeSubscriptionId="sub_lic-solo",
    )

    assert await run("--apply", "--yes") == 0

    out = capsys.readouterr().out
    assert (
        "skip     lic-solo  s***@example.com  shares its payment with lic-other" in out
    )
    assert (
        "skip     lic-other  o***@example.com  shares its payment with lic-solo" in out
    )
    assert env.mail == []


async def test_a_license_with_no_address_is_skipped(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Converting it would leave nobody told."""
    individual_buyer(env, email="")

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  ***  no email on it to send the notice to"
        in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.stripe.calls == []


async def test_a_banned_license_is_skipped_before_stripe_is_read(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env, status="BANNED")

    assert await run("--apply", "--yes") == 0

    assert "skip     lic-solo  s***@example.com  banned" in capsys.readouterr().out
    assert env.stripe.calls == []
    assert env.keygen.writes("lic-solo") == []


async def test_a_license_sold_on_the_decision_day_waits_for_the_flag(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env, created="2026-11-01T00:00:00+00:00")

    assert await run("--apply", "--yes") == 0

    assert "sold on 2026-11-01, after ADR 0080's decision" in capsys.readouterr().out
    assert env.keygen.writes("lic-solo") == []


async def test_one_sold_after_the_decision_that_a_run_started_is_finished_without_the_flag(
    env: Billing,
) -> None:
    """The operator chose to convert it once; a stopped run must not strand it half done."""
    individual_buyer(env, created="2026-11-10T12:00:00+00:00")
    env.keygen.refuse_policy_change["lic-solo"] = 503
    assert await run("--apply", "--yes", "--include-sold-after-decision") == 1
    del env.keygen.refuse_policy_change["lic-solo"]

    assert await run("--apply", "--yes") == 0

    assert held(env)["policy"] == "policy-business"
    assert len(env.mail) == 1


async def test_apply_asks_before_it_changes_anything(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    assert await run("--apply") == 1

    assert {request.method for request in env.keygen.requests} == {"GET"}
    assert env.mail == []
    assert "aborted" in capsys.readouterr().out


# converting ---------------------------------------------------------------------


async def test_apply_makes_the_license_business_solo_and_mails_one_notice(
    env: Billing,
) -> None:
    individual_buyer(env, trialKey="solo@example.com", note="kept by support")
    others(env)

    assert await run("--apply", "--yes") == 0

    license = held(env)
    assert license["policy"] == "policy-business"
    assert license["attributes"]["maxUsers"] == 1
    assert license["attributes"]["key"] == "KEY-lic-solo"
    assert license["attributes"]["metadata"] == {
        "plan": "business",
        "email": "solo@example.com",
        "checkoutSessionId": "cs_lic-solo",
        "stripeCustomerId": "cus_lic-solo",
        "trialKey": "solo@example.com",
        "note": "kept by support",
        "jobs": "JOB_QUESTIONNAIRE",
        # Found through its checkout, and written, as every Business license carries it.
        "stripeSubscriptionId": "sub_lic-solo",
        "convertedFrom": "individual",
        "convertedOn": TODAY,
        "expiryBeforeConversion": EXPIRY,
        "movedToBusinessOn": TODAY,
        "conversionNoticeSentOn": TODAY,
    }
    (mail,) = env.mail
    assert mail.to == "solo@example.com"
    assert mail.subject == "Your SurfSense license is now Business Solo"
    assert [attachment.content for attachment in mail.attachments] == [b"CERT-lic-solo"]
    assert "is now Business Solo, the Business license for one person" in mail.text_body
    # Its buyer may never have read that it renews, so the notice names the day.
    assert renews_on(PERIOD_END) in mail.text_body
    assert PORTAL in mail.text_body
    # Its first license that unlocks a job, so the steps go on to one.
    assert "5. Run your first job." in mail.text_body
    # Its subscription keeps the price it was bought at: Stripe is only read.
    assert {method for method, _ in env.stripe.calls} == {"GET"}
    assert env.keygen.writes("lic-trial") == []
    assert env.keygen.writes("lic-firm") == []


async def test_each_step_is_printed_as_it_is_done(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)

    assert await run("--apply", "--yes") == 0

    assert (
        "lic-solo: marked for conversion; moved to the Business policy; Business Solo, "
        f"1 person, expiry {PERIOD_END.date()} moved to {BUSINESS_EXPIRY.date()}; "
        f"notice mailed, saying it renews on {PERIOD_END.date()}\n"
        in capsys.readouterr().out
    )


async def test_a_cancellation_while_the_prompt_waits_is_what_the_notice_says(
    env: Billing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stripe is read again after the confirmation: the listing may be minutes old."""
    individual_buyer(env)

    def confirm(_question: str) -> str:
        stripe_subscription(env)["cancel_at_period_end"] = True
        return "y"

    monkeypatch.setattr("builtins.input", confirm)

    assert await run("--apply") == 0

    (mail,) = env.mail
    assert ends_on(BUSINESS_EXPIRY) in mail.text_body
    assert RENEWS not in mail.text_body


async def test_a_refund_while_the_prompt_waits_leaves_the_license_alone(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)

    def confirm(_question: str) -> str:
        charge_of(env).update(refunded=True, amount_refunded=6000)
        return "y"

    monkeypatch.setattr("builtins.input", confirm)

    assert await run("--apply") == 1

    assert (
        "lic-solo: failed: Stripe changed since it was listed: subscription "
        "sub_lic-solo, renews on " + str(PERIOD_END.date()) + ", yet a payment for it "
        "was refunded in full or disputed" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


async def test_the_move_answered_with_the_policy_still_keeps_the_license_whole(
    env: Billing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """keygen-api 1.7.2 answers the move with the license under a FIXME to answer the
    policy, so the next step reads the license rather than the answer."""
    individual_buyer(env)
    answer = env.keygen.handle

    def handle(request: httpx2.Request) -> httpx2.Response:
        moved = answer(request)
        if request.method == "PUT" and request.url.path.endswith("/policy"):
            return httpx2.Response(
                200,
                json={
                    "data": {
                        "id": "policy-business",
                        "type": "policies",
                        "attributes": {"metadata": {"surfsensePolicy": "business"}},
                    }
                },
            )
        return moved

    monkeypatch.setattr(env.keygen, "handle", handle)

    assert await run("--apply", "--yes") == 0

    metadata = held(env)["attributes"]["metadata"]
    assert metadata["email"] == "solo@example.com"
    assert metadata["checkoutSessionId"] == "cs_lic-solo"
    assert metadata["plan"] == "business"
    assert "surfsensePolicy" not in metadata
    assert len(env.mail) == 1


async def test_a_license_that_ended_with_its_period_gets_the_30_days_business_has(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """A Business Solo bought for the same year would end 30 days after it."""
    individual_buyer(env)

    assert await run("--apply", "--yes") == 0

    assert expiry_of(env) == BUSINESS_EXPIRY
    assert (
        f"Business Solo, 1 person, expiry {PERIOD_END.date()} moved to "
        f"{BUSINESS_EXPIRY.date()}" in capsys.readouterr().out
    )


async def test_an_expiry_already_past_the_paid_period_is_kept(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    later = BUSINESS_EXPIRY + timedelta(days=10)
    individual_buyer(env, expiry=later.isoformat())

    assert await run("--apply", "--yes") == 0

    assert expiry_of(env) == later
    assert f"expiry {later.date()} kept" in capsys.readouterr().out


async def test_a_license_with_no_expiry_gets_the_one_its_period_paid_for(
    env: Billing,
) -> None:
    """An Individual policy with no duration minted it never to end; Business ends."""
    individual_buyer(env, expiry=None)

    assert await run("--apply", "--yes") == 0

    assert expiry_of(env) == BUSINESS_EXPIRY
    assert held(env)["attributes"]["metadata"]["expiryBeforeConversion"] == "none"
    assert len(env.mail) == 1


async def test_the_expiry_is_written_before_the_file_is_checked_out(
    env: Billing,
) -> None:
    individual_buyer(env)

    await run("--apply", "--yes")

    requests = env.keygen.requests
    written = next(
        index
        for index, request in enumerate(requests)
        if request.method == "PATCH"
        and "expiry" in json.loads(request.content)["data"]["attributes"]
    )
    checked_out = next(
        index
        for index, request in enumerate(requests)
        if request.url.path.endswith("/check-out")
    )
    assert written < checked_out


async def test_the_move_is_keygens_policy_change_on_the_same_license(
    env: Billing,
) -> None:
    individual_buyer(env)

    await run("--apply", "--yes")

    (move,) = [request for request in env.keygen.requests if request.method == "PUT"]
    assert move.url.path == "/v1/accounts/acct/licenses/lic-solo/policy"
    assert json.loads(move.content) == {
        "data": {"type": "policies", "id": "policy-business"}
    }


async def test_a_license_sold_with_its_subscription_id_is_read_by_it(
    env: Billing,
) -> None:
    individual_buyer(env, stripeSubscriptionId="sub_lic-solo")

    assert await run("--apply", "--yes") == 0

    metadata = held(env)["attributes"]["metadata"]
    assert metadata["stripeSubscriptionId"] == "sub_lic-solo"
    assert ("GET", "/v1/checkout/sessions/cs_lic-solo") not in env.stripe.calls
    assert len(env.mail) == 1


async def test_a_second_run_converts_and_mails_nothing(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    assert await run("--apply", "--yes") == 0
    seen = len(env.keygen.requests)
    capsys.readouterr()

    assert await run("--apply", "--yes") == 0

    assert {request.method for request in env.keygen.requests[seen:]} == {"GET"}
    assert len(env.mail) == 1
    assert (
        f"skip     lic-solo  s***@example.com  already converted and mailed on {TODAY}"
        in capsys.readouterr().out.splitlines()
    )


# a buyer whose license does not renew -------------------------------------------


@pytest.mark.parametrize(
    ("turned_off", "state"),
    [
        ({"cancel_at_period_end": True}, "set to cancel"),
        ({"cancel_at": int(PERIOD_END.timestamp())}, "set to cancel"),
        ({"status": "canceled"}, "canceled"),
    ],
)
async def test_a_buyer_who_turned_renewal_off_is_converted_and_told_when_it_ends(
    env: Billing, capsys: pytest.CaptureFixture, turned_off: dict, state: str
) -> None:
    individual_buyer(env)
    stripe_subscription(env).update(turned_off)

    assert await run("--apply", "--yes") == 0

    assert (
        f"subscription sub_lic-solo is {state}, so it does not renew"
        in capsys.readouterr().out
    )
    assert held(env)["policy"] == "policy-business"
    assert expiry_of(env) == BUSINESS_EXPIRY
    (mail,) = env.mail
    assert ends_on(BUSINESS_EXPIRY) in mail.text_body
    assert "only new job runs stop" in mail.text_body
    assert RENEWS not in mail.text_body
    assert "To add or remove people" not in mail.text_body
    # Stripe's portal lets a buyer renew a subscription set to cancel until its period
    # ends, not until the license's grace runs out; a cancelled one has nothing left to
    # renew.
    keep = (
        "To keep it, renew it in the billing portal before "
        f"{PERIOD_END.day} {PERIOD_END:%B %Y}: {PORTAL}"
    )
    assert (keep in mail.text_body) == (state == "set to cancel")
    assert (PORTAL in mail.text_body) == (state == "set to cancel")


async def test_a_subscription_cancelled_after_its_period_moved_on_ends_with_its_end(
    env: Billing,
) -> None:
    """Failed renewal retries cancel it after Stripe moved its period to a year not
    paid for, so the period it holds is not what was paid."""
    unpaid_year_end = NOW + timedelta(days=340)
    ended = NOW - timedelta(days=2)
    individual_buyer(
        env,
        expiry=(NOW + timedelta(days=10)).isoformat(),
        subscription_status="canceled",
    )
    stripe_subscription(env)["items"]["data"][0]["current_period_end"] = int(
        unpaid_year_end.timestamp()
    )
    stripe_subscription(env)["ended_at"] = int(ended.timestamp())

    assert await run("--apply", "--yes") == 0

    assert expiry_of(env) == ended + GRACE
    (mail,) = env.mail
    assert ends_on(ended + GRACE) in mail.text_body


async def test_a_buyer_who_paid_once_is_converted_and_told_when_it_ends(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    paid_once(env)

    assert await run("--apply", "--yes") == 0

    out = capsys.readouterr().out
    assert (
        f"expires {PERIOD_END.date()}  paid once, with no subscription, so it does "
        "not renew" in out
    )
    assert expiry_of(env) == PERIOD_END
    assert "stripeSubscriptionId" not in held(env)["attributes"]["metadata"]
    (mail,) = env.mail
    assert ends_on(PERIOD_END) in mail.text_body
    # Nothing renews and nothing can be renewed, so the notice names no portal.
    assert PORTAL not in mail.text_body


async def test_one_paid_once_that_never_expires_is_left_to_support(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env, expiry=None)
    paid_once(env)

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  paid once, with no subscription, so it "
        "does not renew, yet the license never expires, so as Business it would "
        "never end: a support case" in capsys.readouterr().out
    )
    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []


# a run that stopped --------------------------------------------------------------


async def test_a_license_left_with_only_its_marks_is_finished_by_the_next_run(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    env.keygen.refuse_policy_change["lic-solo"] = 503

    assert await run("--apply", "--yes") == 1

    license = held(env)
    assert license["policy"] == "policy-individual"
    assert license["attributes"]["metadata"]["convertedFrom"] == "individual"
    assert env.mail == []
    assert (
        "lic-solo: marked for conversion; failed: moving it to the Business "
        "policy: Keygen answered 503" in capsys.readouterr().out
    )

    del env.keygen.refuse_policy_change["lic-solo"]
    assert await run("--apply", "--yes") == 0

    assert license["policy"] == "policy-business"
    assert license["attributes"]["maxUsers"] == 1
    assert expiry_of(env) == BUSINESS_EXPIRY
    metadata = license["attributes"]["metadata"]
    assert metadata["plan"] == "business"
    assert metadata["expiryBeforeConversion"] == EXPIRY
    assert metadata["conversionNoticeSentOn"] == TODAY
    assert len(env.mail) == 1
    assert "(half converted by an earlier run)" in capsys.readouterr().out


async def test_a_move_keygen_refuses_leaves_a_license_that_unlocks_no_job(
    env: Billing,
) -> None:
    """Until the license is on the Business policy, every reader still sees Individual."""
    individual_buyer(env)
    env.keygen.refuse_policy_change["lic-solo"] = 422

    assert await run("--apply", "--yes") == 1

    license = held(env)
    assert license["policy"] == "policy-individual"
    assert license["attributes"]["maxUsers"] is None
    assert license["attributes"]["metadata"]["plan"] == "individual"
    assert "jobs" not in license["attributes"]["metadata"]
    assert await license_verdict("KEY-lic-solo") == LicenseVerdict("VALID", ())
    assert env.mail == []


async def test_a_renewal_paid_between_two_runs_is_kept(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """The next run finishes the license without cutting the year just paid for."""
    individual_buyer(env)
    env.keygen.refuse_policy_change["lic-solo"] = 503
    assert await run("--apply", "--yes") == 1
    next_end = PERIOD_END + timedelta(days=365)
    env.stripe.subscriptions["sub_lic-solo"] = subscription(
        "sub_lic-solo", period_end=int(next_end.timestamp()), price=INDIVIDUAL_PRICE
    )
    response = await post_event(
        event(
            "invoice.paid",
            invoice("in_y2", "sub_lic-solo", reason="subscription_cycle"),
        )
    )
    assert response.status_code == 200
    assert expiry_of(env) == next_end + GRACE
    del env.keygen.refuse_policy_change["lic-solo"]
    capsys.readouterr()

    assert await run("--apply", "--yes") == 0

    assert expiry_of(env) == next_end + GRACE
    assert f"expiry {(next_end + GRACE).date()} kept" in capsys.readouterr().out
    assert held(env)["policy"] == "policy-business"
    # It renewed as Individual, then converted.
    assert [mail.subject for mail in env.mail] == [
        "Your SurfSense license has renewed",
        "Your SurfSense license is now Business Solo",
    ]
    assert RENEWS in env.mail[1].text_body


async def test_a_license_moved_but_not_mailed_is_mailed_once_by_the_next_run(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(deliver, "get_mailer", lambda: MailDown())

    assert await run("--apply", "--yes") == 1

    license = held(env)
    assert license["policy"] == "policy-business"
    assert license["attributes"]["maxUsers"] == 1
    assert "conversionNoticeSentOn" not in license["attributes"]["metadata"]
    assert "failed: mailing the notice: timed out" in capsys.readouterr().out

    monkeypatch.setattr(deliver, "get_mailer", lambda: env.mail)
    writes = len(env.keygen.writes("lic-solo"))
    assert await run("--apply", "--yes") == 0

    (mail,) = env.mail
    assert mail.subject == "Your SurfSense license is now Business Solo"
    # Only the mark that the notice went: nothing done before is done again.
    (marked,) = env.keygen.writes("lic-solo")[writes:]
    attributes = json.loads(marked.content)["data"]["attributes"]
    assert list(attributes) == ["metadata"]
    assert attributes["metadata"]["conversionNoticeSentOn"] == TODAY


async def test_a_half_converted_license_whose_subscription_ended_is_finished_and_told_it_ends(
    env: Billing,
) -> None:
    individual_buyer(env)
    env.keygen.refuse_policy_change["lic-solo"] = 503
    await run("--apply", "--yes")
    del env.keygen.refuse_policy_change["lic-solo"]
    env.stripe.subscriptions["sub_lic-solo"]["status"] = "canceled"

    assert await run("--apply", "--yes") == 0

    license = held(env)
    assert license["policy"] == "policy-business"
    assert license["attributes"]["maxUsers"] == 1
    (mail,) = env.mail
    assert ends_on(BUSINESS_EXPIRY) in mail.text_body
    assert RENEWS not in mail.text_body


async def test_a_license_stripe_is_still_retrying_waits_for_a_later_run(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    """Past due may yet renew or end, so no notice fits; it is skipped, not failed."""
    individual_buyer(env)
    env.keygen.refuse_policy_change["lic-solo"] = 503
    await run("--apply", "--yes")
    del env.keygen.refuse_policy_change["lic-solo"]
    env.stripe.subscriptions["sub_lic-solo"]["status"] = "past_due"
    writes = len(env.keygen.writes("lic-solo"))
    capsys.readouterr()

    assert await run("--apply", "--yes") == 0

    assert (
        "skip     lic-solo  s***@example.com  subscription sub_lic-solo is past_due, "
        "neither renewing nor ended; run again once Stripe settles it  "
        "(half converted by an earlier run)" in capsys.readouterr().out
    )
    assert len(env.keygen.writes("lic-solo")) == writes
    assert env.mail == []

    env.stripe.subscriptions["sub_lic-solo"]["status"] = "active"
    assert await run("--apply", "--yes") == 0

    assert held(env)["policy"] == "policy-business"
    (mail,) = env.mail
    assert RENEWS in mail.text_body


# Keygen's answers ----------------------------------------------------------------


async def test_a_license_keygen_refuses_is_reported_and_the_others_still_convert(
    env: Billing, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env, "lic-first", email="first@example.com")
    individual_buyer(env, "lic-second", email="second@example.com")
    env.keygen.refuse_policy_change["lic-first"] = 422

    assert await run("--apply", "--yes") == 1

    out = capsys.readouterr().out
    assert (
        "lic-first: marked for conversion; failed: moving it to the Business "
        "policy: Keygen answered 422: cannot change to a policy with a different "
        "scheme (POLICY_NOT_COMPATIBLE)" in out
    )
    assert held(env, "lic-first")["policy"] == "policy-individual"
    assert held(env, "lic-second")["policy"] == "policy-business"
    assert [mail.to for mail in env.mail] == ["second@example.com"]
    assert "1 of 2 licenses converted, 1 failed" in out


async def test_an_answer_keygen_should_never_give_fails_only_its_license(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A proxy's page in place of a license, say: reported, and the run goes on."""
    individual_buyer(env, "lic-first", email="first@example.com")
    individual_buyer(env, "lic-second", email="second@example.com")
    answer = env.keygen.handle

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET" and request.url.path.endswith("/licenses/lic-first"):
            env.keygen.requests.append(request)
            return httpx2.Response(200, text="<html>proxy</html>")
        return answer(request)

    monkeypatch.setattr(env.keygen, "handle", handle)

    assert await run("--apply", "--yes") == 1

    assert "lic-first: failed: JSONDecodeError: " in capsys.readouterr().out
    assert env.keygen.writes("lic-first") == []
    assert held(env, "lic-second")["policy"] == "policy-business"
    assert [mail.to for mail in env.mail] == ["second@example.com"]


async def test_a_license_suspended_after_it_was_listed_is_left_alone(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A refund can land between the listing and the confirmation."""
    individual_buyer(env)
    answer = env.keygen.handle

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET" and request.url.path.endswith("/licenses/lic-solo"):
            held(env)["attributes"]["status"] = "SUSPENDED"
        return answer(request)

    monkeypatch.setattr(env.keygen, "handle", handle)

    assert await run("--apply", "--yes") == 1

    assert env.keygen.writes("lic-solo") == []
    assert env.mail == []
    assert (
        "lic-solo: failed: suspended since it was listed; left as it is"
        in capsys.readouterr().out
    )


async def test_a_license_keygen_will_not_validate_gets_no_notice(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(
        env.keygen,
        "_validation",
        lambda record: httpx2.Response(
            200, json={"data": None, "meta": {"valid": False, "code": "SUSPENDED"}}
        ),
    )

    assert await run("--apply", "--yes") == 1

    assert (
        "failed: not mailed: Keygen no longer validates it, so it gets no file"
        in capsys.readouterr().out
    )
    assert env.mail == []
    assert "conversionNoticeSentOn" not in held(env)["attributes"]["metadata"]


async def test_a_notice_mark_keygen_drops_once_is_written_on_a_retry(
    env: Billing, monkeypatch: pytest.MonkeyPatch
) -> None:
    individual_buyer(env)
    refused = failing_notice_marks(env, monkeypatch, times=1)

    assert await run("--apply", "--yes") == 0

    assert len(refused) == 1
    assert held(env)["attributes"]["metadata"]["conversionNoticeSentOn"] == TODAY
    assert len(env.mail) == 1


async def test_a_notice_mark_keygen_keeps_refusing_says_how_to_write_it(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    refused = failing_notice_marks(env, monkeypatch, times=3)

    assert await run("--apply", "--yes") == 1

    assert len(refused) == 3
    assert (
        f"notice mailed, saying it renews on {PERIOD_END.date()}; failed: recording "
        "the notice: Keygen answered 503; the notice was sent: record it with "
        f"`{SCRIPT} --mark-notice-sent lic-solo {TODAY}`, or the next run sends it "
        "again" in capsys.readouterr().out
    )
    assert len(env.mail) == 1


async def test_a_notice_mark_keygen_answers_without_the_license_is_retried_and_named(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Any failure after the mail went, not only a refusal, must leave the way to record it."""
    individual_buyer(env)
    refused = failing_notice_marks(
        env, monkeypatch, times=3, refusal=lambda: httpx2.Response(200, json={})
    )

    assert await run("--apply", "--yes") == 1

    out = capsys.readouterr().out
    assert len(refused) == 3
    assert (
        f"notice mailed, saying it renews on {PERIOD_END.date()}; failed: recording "
        "the notice: KeyError: 'data'; the notice was sent: record it with "
        f"`{SCRIPT} --mark-notice-sent lic-solo {TODAY}`" in out
    )
    assert len(env.mail) == 1


class Killed(BaseException):
    """The run stopped from outside, as by Ctrl+C or a closed terminal."""


async def test_a_run_stopped_after_the_notice_went_has_already_said_so(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)

    def killed() -> httpx2.Response:
        raise Killed

    failing_notice_marks(env, monkeypatch, times=1, refusal=killed)

    with pytest.raises(Killed):
        await run("--apply", "--yes")

    assert (
        f"lic-solo: marked for conversion; moved to the Business policy; Business "
        f"Solo, 1 person, expiry {PERIOD_END.date()} moved to "
        f"{BUSINESS_EXPIRY.date()}; notice mailed, saying it renews on "
        f"{PERIOD_END.date()}" in capsys.readouterr().out
    )
    assert len(env.mail) == 1


async def test_the_notice_mark_named_by_a_run_is_recorded_with_every_key_kept(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Keygen replaces metadata whole, and CE has no dashboard to set one key in."""
    individual_buyer(env)
    failing_notice_marks(env, monkeypatch, times=3)
    assert await run("--apply", "--yes") == 1
    before = dict(held(env)["attributes"]["metadata"])
    capsys.readouterr()

    assert await run("--mark-notice-sent", "lic-solo", TODAY) == 0

    assert held(env)["attributes"]["metadata"] == {
        **before,
        "conversionNoticeSentOn": TODAY,
    }
    assert f"lic-solo: notice recorded as sent on {TODAY}" in capsys.readouterr().out
    assert await run("--apply", "--yes") == 0
    assert len(env.mail) == 1


@pytest.mark.parametrize("state", ["individual", "already-recorded"])
async def test_the_notice_mark_is_refused_for_a_license_it_does_not_fit(
    env: Billing, capsys: pytest.CaptureFixture, state: str
) -> None:
    """A mistyped id must not make the next run skip a license as already mailed."""
    individual_buyer(env)
    if state == "already-recorded":
        assert await run("--apply", "--yes") == 0
    writes = len(env.keygen.writes("lic-solo"))

    assert await run("--mark-notice-sent", "lic-solo", "2026-11-20") == 1

    said = {
        "individual": "error: lic-solo is not a license a run made Business Solo",
        "already-recorded": "error: lic-solo's notice is already recorded, as sent on "
        f"{TODAY}",
    }[state]
    assert said in capsys.readouterr().err
    assert len(env.keygen.writes("lic-solo")) == writes


@pytest.mark.parametrize(
    "argv",
    [
        ("--mark-notice-sent", "lic-solo", "20 Nov"),
        ("--mark-notice-sent", "lic-solo", TODAY, "--apply"),
    ],
)
async def test_the_notice_mark_takes_a_day_and_goes_alone(
    env: Billing, argv: tuple[str, ...]
) -> None:
    individual_buyer(env)

    with pytest.raises(SystemExit) as refused:
        await run(*argv)

    assert refused.value.code == 2
    assert env.keygen.requests == []


async def test_a_notice_the_mailer_did_not_take_is_never_recorded_as_sent(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Mail was on at the start and is off when the notice goes."""
    individual_buyer(env)
    monkeypatch.setattr(deliver, "is_mail_enabled", lambda: False)

    assert await run("--apply", "--yes") == 1

    assert "conversionNoticeSentOn" not in held(env)["attributes"]["metadata"]
    assert env.mail == []
    assert "failed: not mailed: mail is off" in capsys.readouterr().out


async def test_a_license_mailed_since_it_was_listed_is_not_mailed_again(
    env: Billing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another run, or support, finished it between the listing and the confirmation."""
    individual_buyer(env)
    answer = env.keygen.handle

    def finished_meanwhile(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET" and request.url.path.endswith("/licenses/lic-solo"):
            license = held(env)
            license["policy"] = "policy-business"
            license["attributes"]["metadata"].update(
                plan="business",
                jobs="JOB_QUESTIONNAIRE",
                stripeSubscriptionId="sub_lic-solo",
                convertedFrom="individual",
                movedToBusinessOn=TODAY,
                conversionNoticeSentOn=TODAY,
            )
        return answer(request)

    monkeypatch.setattr(env.keygen, "handle", finished_meanwhile)

    assert await run("--apply", "--yes") == 0

    assert env.mail == []
    assert env.keygen.writes("lic-solo") == []


# after the conversion -------------------------------------------------------------


async def test_a_converted_license_renews_on_its_key_as_business(env: Billing) -> None:
    individual_buyer(env)
    assert await run("--apply", "--yes") == 0
    env.mail.clear()
    next_end = PERIOD_END + timedelta(days=365)
    env.stripe.subscriptions["sub_lic-solo"] = subscription(
        "sub_lic-solo", period_end=int(next_end.timestamp()), price=INDIVIDUAL_PRICE
    )

    response = await post_event(
        event(
            "invoice.paid",
            invoice("in_y2", "sub_lic-solo", reason="subscription_cycle"),
        )
    )

    assert response.status_code == 200
    assert list(env.keygen.licenses) == ["lic-solo"]
    assert expiry_of(env) == next_end + GRACE
    assert held(env)["attributes"]["maxUsers"] == 1
    (mail,) = env.mail
    assert mail.subject == "Your SurfSense Business license has renewed"
    assert PORTAL in mail.text_body


async def test_a_converted_license_follows_its_subscriptions_people(
    env: Billing,
) -> None:
    """Found by the stripeSubscriptionId the conversion wrote: seat changes never trace a checkout."""
    individual_buyer(env)
    assert await run("--apply", "--yes") == 0
    more = subscription(
        "sub_lic-solo",
        period_end=int(PERIOD_END.timestamp()),
        quantity=3,
        price=INDIVIDUAL_PRICE,
    )
    env.stripe.subscriptions["sub_lic-solo"] = more

    response = await post_event(event("customer.subscription.updated", more))

    assert response.status_code == 200
    assert held(env)["attributes"]["maxUsers"] == 3


async def test_a_refund_of_its_first_year_suspends_a_converted_license(
    env: Billing,
) -> None:
    individual_buyer(env)
    assert await run("--apply", "--yes") == 0
    env.stripe.invoices["in_y1"] = invoice(
        "in_y1", "sub_lic-solo", reason="subscription_create"
    )
    env.stripe.invoice_paid_by["pi_y1"] = "in_y1"

    response = await post_event(
        event(
            "charge.refunded",
            {
                "id": "ch_y1",
                "object": "charge",
                "payment_intent": "pi_y1",
                "refunded": True,
                "amount": 6000,
                "amount_refunded": 6000,
            },
        )
    )

    assert response.status_code == 200
    assert held(env)["attributes"]["status"] == "SUSPENDED"


async def test_a_converted_license_gets_its_job_and_resends_as_business(
    env: Billing,
) -> None:
    individual_buyer(env)
    assert await run("--apply", "--yes") == 0

    verdict = await license_verdict("KEY-lic-solo")
    (resent,) = await licenses_for_email("solo@example.com")

    assert verdict == LicenseVerdict("VALID", ("JOB_QUESTIONNAIRE",))
    assert BusinessCopy.of(resent) == BusinessCopy(people=1, paid=True)


# refusing to start ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("KEYGEN_POLICY_INDIVIDUAL", ""),
        ("KEYGEN_POLICY_BUSINESS", ""),
        ("KEYGEN_POLICY_BUSINESS", "policy-individual"),
        ("STRIPE_SECRET_KEY", ""),
    ],
)
async def test_a_missing_setting_refuses_to_start(
    env: Billing,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    setting: str,
    value: str,
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(config, setting, value)

    assert await run("--apply", "--yes") == 2

    assert setting in capsys.readouterr().err
    assert env.keygen.requests == []
    assert env.stripe.calls == []


async def test_no_job_to_unlock_refuses_to_start(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(jobs, "JOBS", {})

    assert await run() == 2

    assert "lists no job" in capsys.readouterr().err
    assert env.keygen.requests == []


async def test_apply_with_mail_off_refuses_to_start(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A notice that is never sent must never be recorded as sent."""
    individual_buyer(env)
    monkeypatch.setattr(script, "is_mail_enabled", lambda: False)

    assert await run("--apply", "--yes") == 2

    assert "SMTP_ENABLED" in capsys.readouterr().err
    assert env.keygen.requests == []


async def test_apply_with_mail_settings_that_build_no_mailer_refuses_to_start(
    env: Billing, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    individual_buyer(env)

    def no_mailer():
        raise ValueError("SMTP_HOST is not set")

    monkeypatch.setattr(script, "get_mailer", no_mailer)

    assert await run("--apply", "--yes") == 2

    assert (
        "The SMTP settings are invalid, so no notice could be sent: SMTP_HOST is not set"
        in capsys.readouterr().err
    )
    assert env.keygen.requests == []


async def test_yes_without_apply_is_refused(env: Billing) -> None:
    with pytest.raises(SystemExit) as refused:
        await run("--yes")

    assert refused.value.code == 2
    assert env.keygen.requests == []


@pytest.mark.parametrize(
    "answer",
    [httpx2.Response(503), httpx2.Response(200, text="<html>proxy</html>")],
    ids=["down", "not-json"],
)
async def test_policies_keygen_cannot_answer_for_stop_the_run(
    env: Billing,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    answer: httpx2.Response,
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(env.keygen, "handle", lambda request: answer)

    assert await run() == 1

    assert "error: could not read the policies in Keygen" in capsys.readouterr().err
    assert env.stripe.calls == []


@pytest.mark.parametrize("apply", [(), ("--apply", "--yes")], ids=["dry", "apply"])
async def test_a_license_stripe_failed_for_fails_the_run_while_the_others_convert(
    env: Billing, monkeypatch: pytest.MonkeyPatch, apply: tuple[str, ...]
) -> None:
    individual_buyer(env)
    individual_buyer(env, "lic-unread", email="unread@example.com")
    answer = env.stripe._answer

    def refuse_one(method, path, query):
        if path.endswith("/cs_lic-unread"):
            return 400, {"error": {"type": "invalid_request_error", "message": "no"}}
        return answer(method, path, query)

    monkeypatch.setattr(env.stripe, "_answer", refuse_one)

    assert await run(*apply) == 1

    assert [mail.to for mail in env.mail] == (["solo@example.com"] if apply else [])
    assert env.keygen.writes("lic-unread") == []


@pytest.mark.parametrize(
    ("business", "said"),
    [
        (
            "policy-business-trial",
            "KEYGEN_POLICY_BUSINESS names Business trial, whose surfsensePolicy is "
            "business-trial, not the Business policy",
        ),
        (
            "policy-unknown",
            "KEYGEN_POLICY_BUSINESS names a policy Keygen does not show this token: "
            "none, or another product's",
        ),
    ],
)
async def test_a_business_setting_naming_another_policy_refuses_to_start(
    env: Billing,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    business: str,
    said: str,
) -> None:
    individual_buyer(env)
    monkeypatch.setattr(config, "KEYGEN_POLICY_BUSINESS", business)

    assert await run() == 2

    assert said in capsys.readouterr().err
    assert not any("/licenses" in request.url.path for request in env.keygen.requests)
    assert env.stripe.calls == []


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("scheme", "RSA_2048_PKCS1_SIGN_V2"),
        ("encrypted", True),
        ("usePool", True),
        ("machineUniquenessStrategy", "UNIQUE_PER_ACCOUNT"),
        ("componentUniquenessStrategy", "UNIQUE_PER_LICENSE"),
        ("transferStrategy", "RESET_EXPIRY"),
    ],
)
async def test_a_business_policy_the_moves_cannot_use_refuses_to_start(
    env: Billing,
    capsys: pytest.CaptureFixture,
    attribute: str,
    value: object,
) -> None:
    """Keygen would refuse every move, or give every license a new expiry."""
    individual_buyer(env)
    env.keygen.policies["policy-business"][attribute] = value

    assert await run("--apply", "--yes") == 2

    assert f"The Business policy's {attribute}" in capsys.readouterr().err
    assert not any("/licenses" in request.url.path for request in env.keygen.requests)
    assert env.stripe.calls == []
