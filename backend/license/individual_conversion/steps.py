"""Making one license Business Solo, in steps a later run can resume.

a. the conversion marks in its metadata, with the expiry it had;
b. the Business policy, on the same key;
c. Business's plan and jobs, one person, and the expiry its paid period buys
   Business, in one update;
d. a fresh file mailed with the conversion notice, then its mark.

Each step is skipped once done: a, c and d by their marks, b by the license's
policy. Stripe is read again first, since the listing may be minutes old. Until
c, every reader still sees an Individual license, so a move Keygen refuses
unlocks nothing. The Stripe subscription is never touched.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

import anyio
import httpx2

from license import keygen
from license.email.deliver import deliver_licenses
from license.email.message import BusinessCopy
from license.models import META_CONVERSION_NOTICE_SENT_ON, LicenseRecord
from license.records import issued_for_id, license_record

from .business_expiry import business_expiry
from .live_subscription import LiveSubscription, live_subscription
from .progress import (
    business_metadata,
    conversion_marks,
    instant,
    marked,
    moved,
    notice_sent_on,
    started,
)
from .selection import Candidate, reason_to_leave_purchase

_NOT_IN_GOOD_STANDING = frozenset({"SUSPENDED", "BANNED"})
# A mark not written means the next run mails the notice again, so a brief
# Keygen failure is waited out first.
_NOTICE_MARK_RETRY_SECONDS = (0.5, 1.5)
_SCRIPT = "python -m license.scripts.convert_individual_licenses"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What this run did to one license, and the step that failed, if one did."""

    done: tuple[str, ...]
    failure: str | None = None


class _StepError(RuntimeError):
    pass


async def convert_license(
    candidate: Candidate,
    *,
    business_policy: str,
    stripe_client: Any,
    now: datetime,
    on_step: Callable[[str], None] | None = None,
) -> Outcome:
    """Every step not yet done, in order; a failure leaves the license where it got to.

    ``on_step`` hears each step as it is done, so a run killed after a notice
    went out still shows that it did.
    """
    done: list[str] = []

    def did(step: str) -> None:
        done.append(step)
        if on_step is not None:
            on_step(step)

    try:
        await _convert(candidate, business_policy, stripe_client, now, did)
    except _StepError as failure:
        return Outcome(tuple(done), str(failure))
    except Exception as error:
        # Not a refusal a step names, such as an answer Keygen should never give.
        return Outcome(tuple(done), f"{type(error).__name__}: {error}")
    return Outcome(tuple(done))


async def mark_notice_sent(license_id: str, day: date) -> str | None:
    """Step d's mark, written by hand when a run mailed the notice but could not; why not, if not."""
    try:
        record = await _current(license_id)
        if not (started(record) and moved(record)):
            return f"{license_id} is not a license a run made Business Solo"
        sent_on = notice_sent_on(record)
        if sent_on is not None:
            return f"{license_id}'s notice is already recorded, as sent on {sent_on}"
        await _step(
            "recording the notice",
            keygen.update_license(
                license_id,
                metadata=marked(record, META_CONVERSION_NOTICE_SENT_ON, day),
            ),
        )
    except _StepError as failure:
        return str(failure)
    return None


async def _convert(
    candidate: Candidate,
    business_policy: str,
    stripe_client: Any,
    now: datetime,
    did: Callable[[str], None],
) -> None:
    license_id = candidate.record.keygen_license_id
    today = now.date()
    # Read again: the list may be minutes old by the time it was confirmed.
    record = await _current(license_id)
    status = (record.status or "").upper()
    if status in _NOT_IN_GOOD_STANDING:
        raise _StepError(f"{status.lower()} since it was listed; left as it is")
    subscription = await _purchase_now(record, stripe_client, now)

    if not started(record):
        marks = conversion_marks(record, subscription_id=subscription.id, today=today)
        record = await _step(
            "writing its conversion marks",
            keygen.update_license(license_id, metadata=marks),
        )
        did("marked for conversion")

    if record.policy != business_policy:
        await _step(
            "moving it to the Business policy",
            keygen.change_license_policy(license_id, business_policy),
        )
        did("moved to the Business policy")
        # Read, not taken from the answer: keygen-api 1.7.2 answers the license
        # under a FIXME saying it should answer the policy.
        record = await _current(license_id)

    if not moved(record):
        record = await _make_business_solo(record, subscription, today, did)

    if notice_sent_on(record) is None:
        did(await _mail_notice(record, subscription))
        await _record_notice(license_id, today)


async def _purchase_now(
    record: LicenseRecord, stripe_client: Any, now: datetime
) -> LiveSubscription:
    """What Stripe says now: a cancellation or a refund since the listing changes the notice."""
    try:
        subscription = await live_subscription(record.metadata, stripe_client)
    except Exception as error:
        raise _StepError(f"reading Stripe: {error}") from error
    reason = reason_to_leave_purchase(record, subscription, now)
    if reason is not None:
        raise _StepError(f"Stripe changed since it was listed: {reason}; left as it is")
    return subscription


async def _make_business_solo(
    record: LicenseRecord,
    subscription: LiveSubscription,
    today: date,
    did: Callable[[str], None],
) -> LicenseRecord:
    expiry = business_expiry(record, subscription)
    changes: dict[str, Any] = {
        "max_users": 1,
        "metadata": business_metadata(record, today=today),
    }
    if expiry is not None:
        changes["expiry"] = expiry
    updated = await _step(
        "making it Business Solo",
        keygen.update_license(record.keygen_license_id, **changes),
    )
    had = _day(instant(record.expiry))
    did(
        f"Business Solo, 1 person, expiry {had} moved to {_day(expiry)}"
        if expiry is not None
        else f"Business Solo, 1 person, expiry {had} kept"
    )
    return updated


async def _mail_notice(record: LicenseRecord, subscription: LiveSubscription) -> str:
    """What was mailed: the notice names the day it renews, or the day it ends."""
    license_id = record.keygen_license_id
    issued = await _keygen_call("checking out its file", issued_for_id(license_id))
    if issued is None:
        raise _StepError(
            "not mailed: Keygen no longer validates it, so it gets no file"
        )
    copy = BusinessCopy.of(issued)
    if copy is None:
        raise _StepError("not mailed: Keygen does not hold it as Business")
    if subscription.renews:
        renews = subscription.period_end
        if renews is None:
            raise _StepError("not mailed: it renews, yet Stripe names no day it does")
        copy = replace(copy, renews_on=renews.date())
        said = f"notice mailed, saying it renews on {renews.date()}"
    else:
        ends = instant(record.expiry)
        if ends is None:
            raise _StepError("not mailed: it does not renew, yet has no expiry to name")
        # Stripe's portal renews a subscription set to cancel only until its period
        # ends, a month before the license does.
        until = subscription.period_end if subscription.resumable else None
        copy = replace(
            copy,
            ends_on=ends.date(),
            resumable_until=until.date() if until is not None else None,
        )
        said = f"notice mailed, saying it ends on {ends.date()}"
    try:
        sent = await deliver_licenses(
            "conversion",
            to=issued.email,
            certificates=[issued.certificate],
            business=copy,
            idempotency_key=f"conversion:{license_id}",
        )
    except Exception as error:
        raise _StepError(f"mailing the notice: {error}") from error
    if not sent:
        raise _StepError("not mailed: mail is off")
    return said


async def _record_notice(license_id: str, today: date) -> None:
    for wait in (*_NOTICE_MARK_RETRY_SECONDS, None):
        try:
            current = await _current(license_id)
            await _step(
                "recording the notice",
                keygen.update_license(
                    license_id,
                    metadata=marked(current, META_CONVERSION_NOTICE_SENT_ON, today),
                ),
            )
            return
        except Exception as failure:
            # Any failure, not only a refusal: the notice went, so the next run
            # mails it again unless the mark is written or named.
            if wait is None:
                said = (
                    str(failure)
                    if isinstance(failure, _StepError)
                    else f"recording the notice: {type(failure).__name__}: {failure}"
                )
                raise _StepError(
                    f"{said}; the notice was sent: record it with "
                    f"`{_SCRIPT} --mark-notice-sent {license_id} {today.isoformat()}`, "
                    "or the next run sends it again"
                ) from failure
            await anyio.sleep(wait)


async def _current(license_id: str) -> LicenseRecord:
    found = await _keygen_call("reading it", keygen.get_license(license_id))
    if found is None:
        raise _StepError("Keygen no longer has it")
    return license_record(found)


async def _step(what: str, call: Awaitable[dict[str, Any]]) -> LicenseRecord:
    """One write to the license, and the record Keygen answers with."""
    return license_record(await _keygen_call(what, call))


async def _keygen_call[T](what: str, call: Awaitable[T]) -> T:
    try:
        return await call
    except httpx2.HTTPStatusError as error:
        raise _StepError(f"{what}: {_refusal(error.response)}") from error
    except httpx2.HTTPError as error:
        raise _StepError(f"{what}: {error!r}") from error


def _refusal(response: httpx2.Response) -> str:
    """Keygen's own words for a refusal: each error's detail, and its code."""
    try:
        body = response.json()
    except ValueError:
        body = None
    errors = body.get("errors") if isinstance(body, dict) else None
    details = [
        str(error.get("detail") or error.get("title") or "")
        + (f" ({error['code']})" if error.get("code") else "")
        for error in errors or []
        if isinstance(error, dict)
    ]
    said = "; ".join(detail for detail in details if detail)
    return f"Keygen answered {response.status_code}" + (f": {said}" if said else "")


def _day(moment: datetime | None) -> str:
    return moment.date().isoformat() if moment is not None else "none"
