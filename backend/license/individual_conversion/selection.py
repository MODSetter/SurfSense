"""Which licenses a conversion run takes, and why it leaves the rest.

It takes each license on the Individual policy that is in good standing and was
bought in this Stripe account, its money not given back, whether its purchase
renews or has settled not to, and each license a stopped run left half
converted, found by its marker wherever its policy now is. Trials are on their
own policies, so they are never read. Nothing here writes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from license import keygen
from license.models import (
    META_CONVERTED_FROM,
    META_EMAIL,
    META_PLAN,
    META_SESSION,
    META_SUBSCRIPTION,
    LicenseRecord,
)
from license.records import license_record

from .business_expiry import expiry_once_converted
from .live_subscription import LiveSubscription, live_subscription
from .progress import INDIVIDUAL, instant, notice_sent_on, started

# ADR 0080 leaves a license sold from its decision on to open question q, since
# neither the Individual page nor its purchase mail says it becomes Business Solo.
DECISION_DAY = datetime(2026, 11, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A license to convert, or to finish converting."""

    record: LicenseRecord
    subscription: LiveSubscription


@dataclass(frozen=True, slots=True)
class Skipped:
    """A license the run leaves, and why."""

    record: LicenseRecord
    reason: str


@dataclass(frozen=True, slots=True)
class Selection:
    to_convert: tuple[Candidate, ...]
    skipped: tuple[Skipped, ...]
    # Stripe could not be read for these; they count as failures.
    unread: tuple[Skipped, ...]


async def select_licenses(
    *,
    individual_policy: str,
    stripe_client: Any,
    now: datetime,
    include_sold_after_decision: bool = False,
) -> Selection:
    """Keygen's failures propagate; Stripe's are kept per license, in ``unread``."""
    records: dict[str, LicenseRecord] = {}
    async for found in keygen.iter_licenses(policy=individual_policy):
        record = license_record(found)
        records[record.keygen_license_id] = record
    async for found in keygen.iter_licenses(metadata={META_CONVERTED_FROM: INDIVIDUAL}):
        record = license_record(found)
        records.setdefault(record.keygen_license_id, record)
    read = sorted(
        records.values(), key=lambda held: (held.created or "", held.keygen_license_id)
    )

    taken: list[Candidate] = []
    skipped: list[Skipped] = []
    unread: list[Skipped] = []
    for record in read:
        reason = _reason_to_leave(record, now, include_sold_after_decision)
        if reason is not None:
            skipped.append(Skipped(record, reason))
            continue
        try:
            subscription = await live_subscription(record.metadata, stripe_client)
        except Exception as error:
            unread.append(Skipped(record, f"Stripe could not be read: {error}"))
            continue
        reason = reason_to_leave_purchase(record, subscription, now)
        if reason is not None:
            skipped.append(Skipped(record, reason))
            continue
        taken.append(Candidate(record, subscription))

    shared = _sharing_a_payment(read, taken)
    for candidate in taken:
        others = shared.get(candidate.record.keygen_license_id)
        if others:
            skipped.append(
                Skipped(
                    candidate.record,
                    f"shares its payment with {', '.join(others)}: a support case",
                )
            )
    to_convert = tuple(
        candidate
        for candidate in taken
        if candidate.record.keygen_license_id not in shared
    )
    return Selection(to_convert, tuple(skipped), tuple(unread))


def sold_after_decision(record: LicenseRecord) -> date | None:
    """The day it was sold, when that is ADR 0080's decision day or later."""
    created = instant(record.created)
    if created is None or created < DECISION_DAY:
        return None
    return created.date()


def _reason_to_leave(
    record: LicenseRecord, now: datetime, include_sold_after_decision: bool
) -> str | None:
    sent_on = notice_sent_on(record)
    if sent_on is not None:
        return f"already converted and mailed on {sent_on}"
    status = (record.status or "").upper()
    if status == "SUSPENDED":
        return "suspended (a refund, a dispute, or by hand)"
    if status == "BANNED":
        return "banned"
    expiry = instant(record.expiry)
    if status == "EXPIRED" or (expiry is not None and expiry <= now):
        return f"expired on {expiry.date()}" if expiry is not None else "expired"
    plan = str(record.metadata.get(META_PLAN) or INDIVIDUAL)
    if not started(record) and plan != INDIVIDUAL:
        return f"its plan is {plan}, not individual"
    if not record.metadata.get(META_EMAIL):
        return "no email on it to send the notice to"
    sold_on = sold_after_decision(record)
    if sold_on is not None and not started(record) and not include_sold_after_decision:
        return (
            f"sold on {sold_on}, after ADR 0080's decision of 1 Nov 2026, so its open "
            "question q decides it; --include-sold-after-decision converts it"
        )
    return None


def reason_to_leave_purchase(
    record: LicenseRecord, subscription: LiveSubscription, now: datetime
) -> str | None:
    """Why the notice could not say truly what Stripe will do, or ``None`` to convert it."""
    if not (subscription.renews or subscription.ends):
        return subscription.describe()
    said = subscription.describe()
    if subscription.returned:
        return (
            f"{said}, yet a payment for it was refunded in full or disputed and the "
            "license is not suspended: a support case"
        )
    if subscription.people not in (None, 1):
        return f"{said}, for {subscription.people} people, and Business Solo is one: a support case"
    if subscription.renews and subscription.renews_above_price_paid:
        return (
            f"{said}, yet the year it paid for was discounted and no discount lasts, "
            "so it would not renew at the price paid: a support case"
        )
    if subscription.renews and subscription.period_end is None:
        return f"{said}, yet Stripe names no day it renews: a support case"
    ends_at = expiry_once_converted(record, subscription)
    if subscription.ends and ends_at is None:
        return f"{said}, yet the license never expires, so as Business it would never end: a support case"
    if subscription.ends and ends_at is not None and ends_at <= now:
        return f"{said}, and the time it paid for ended on {ends_at.date()}"
    return None


def _sharing_a_payment(
    read: Iterable[LicenseRecord], taken: Iterable[Candidate]
) -> dict[str, list[str]]:
    """Each license taken whose payment another license read also carries.

    Two licenses on one payment are a support case, never a guess, as in
    ``records.find_license_by_checkout_session``: renewals would act on neither,
    or on one of them by chance.
    """
    traced = {
        candidate.record.keygen_license_id: candidate.subscription.id
        for candidate in taken
    }
    paid_by = {
        record.keygen_license_id: _payments(
            record, traced.get(record.keygen_license_id)
        )
        for record in read
    }
    holders: dict[str, set[str]] = defaultdict(set)
    for license_id, payments in paid_by.items():
        for payment in payments:
            holders[payment].add(license_id)
    shared: dict[str, list[str]] = {}
    for license_id in traced:
        others = {
            holder
            for payment in paid_by[license_id]
            for holder in holders[payment]
            if holder != license_id
        }
        if others:
            shared[license_id] = sorted(others)
    return shared


def _payments(record: LicenseRecord, traced_subscription: str | None) -> set[str]:
    """The Stripe objects that paid for it: its checkout session and its subscription."""
    payments = {
        str(record.metadata.get(META_SESSION) or ""),
        str(record.metadata.get(META_SUBSCRIPTION) or ""),
        traced_subscription or "",
    }
    return payments - {""}
