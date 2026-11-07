"""Make every Individual license already sold Business Solo, on the same key (ADR 0080).

    python -m license.scripts.convert_individual_licenses
    python -m license.scripts.convert_individual_licenses --apply
    python -m license.scripts.convert_individual_licenses --mark-notice-sent LICENSE_ID DAY

Run once at the switch, after the release with the Jobs screen and the first job
pack are out. Without --apply it changes nothing: it lists the licenses it would
convert, addresses masked, and why it skips the rest. --apply asks first, unless
--yes is passed. Only a license bought in this Stripe account, its money not
given back, converts, and its notice names the day it renews or the day it ends;
the subscription is never touched. One sold since 1 Nov 2026 converts only with
--include-sold-after-decision. The next run finishes what a stopped one left; a
license is converted once, and its notice goes twice only in the cases
portal.md's Known gaps names. --mark-notice-sent records a notice a run mailed
but could not record, as that run says.

Exits 1 when any license failed, 2 when a setting or the Business policy is wrong.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime

import httpx2

from license.individual_conversion.business_expiry import (
    business_expiry,
    expiry_once_converted,
)
from license.individual_conversion.business_policy import (
    PolicyMismatchError,
    checked_business_policy,
)
from license.individual_conversion.progress import half_converted, instant
from license.individual_conversion.selection import (
    Candidate,
    Selection,
    select_licenses,
    sold_after_decision,
)
from license.individual_conversion.steps import convert_license, mark_notice_sent
from license.jobs import jobs_metadata
from license.models import META_EMAIL, LicenseRecord
from license.settings import config
from license.stripe_client import get_stripe_client
from mailer import get_mailer, is_mail_enabled


def _refusal(*, apply: bool) -> str | None:
    """What stops the run before it reads anything, if anything does."""
    individual = config.KEYGEN_POLICY_INDIVIDUAL
    business = config.KEYGEN_POLICY_BUSINESS
    if not individual:
        return "Set KEYGEN_POLICY_INDIVIDUAL: the licenses to convert are on it"
    if not business:
        return (
            "Set KEYGEN_POLICY_BUSINESS, the policy they move to; "
            "scripts/setup_business_policies.py prints it"
        )
    if individual == business:
        return "KEYGEN_POLICY_INDIVIDUAL and KEYGEN_POLICY_BUSINESS name one policy"
    if not jobs_metadata():
        return "license/jobs.py lists no job, so a converted license would unlock none"
    if not config.STRIPE_SECRET_KEY:
        return (
            "Set STRIPE_SECRET_KEY: a license converts only when Stripe holds its "
            "purchase, and its notice says what Stripe says of its renewal"
        )
    if apply and not is_mail_enabled():
        return "Mail is off (SMTP_ENABLED), so no notice could be sent"
    if apply:
        try:
            get_mailer()
        except ValueError as error:
            return f"The SMTP settings are invalid, so no notice could be sent: {error}"
    return None


def masked(email: str) -> str:
    """``a***@example.com``: enough to tell licenses apart, not to read an address."""
    local, at, domain = email.partition("@")
    if not at:
        return "***"
    return f"{local[:1]}***@{domain}"


def _day(moment: datetime | None) -> str:
    return moment.date().isoformat() if moment is not None else "none"


def _who(record: LicenseRecord) -> str:
    return f"{record.keygen_license_id}  {masked(str(record.metadata.get(META_EMAIL) or ''))}"


def _expiry(candidate: Candidate) -> str:
    """Its expiry now, and the one step c gives it, when that is later."""
    record, subscription = candidate.record, candidate.subscription
    now = _day(instant(record.expiry))
    if business_expiry(record, subscription) is None:
        return now
    return f"{now} ({_day(expiry_once_converted(record, subscription))} once converted)"


def _plural(count: int) -> str:
    return f"{count} license" if count == 1 else f"{count} licenses"


class _ProgressLine:
    """One license's line, each step printed as it is done: a run killed after a notice went still shows it."""

    def __init__(self, license_id: str) -> None:
        print(f"{license_id}: ", end="", flush=True)
        self._said = 0

    def add(self, step: str) -> None:
        print(("; " if self._said else "") + step, end="", flush=True)
        self._said += 1

    def end(self, failure: str | None) -> None:
        if failure is not None:
            self.add(f"failed: {failure}")
        elif not self._said:
            self.add("nothing left to do")
        print(flush=True)


def _print_selection(selection: Selection) -> None:
    for candidate in selection.to_convert:
        record = candidate.record
        line = (
            f"convert  {_who(record)}  created {_day(instant(record.created))}  "
            f"expires {_expiry(candidate)}  {candidate.subscription.describe()}"
        )
        if sold_after_decision(record) is not None:
            line += "  (sold after ADR 0080's decision of 1 Nov 2026)"
        if half_converted(record):
            line += "  (half converted by an earlier run)"
        print(line)
    for skipped in selection.skipped:
        line = f"skip     {_who(skipped.record)}  {skipped.reason}"
        if half_converted(skipped.record):
            line += "  (half converted by an earlier run)"
        print(line)
    for unread in selection.unread:
        print(f"failed   {_who(unread.record)}  {unread.reason}")
    print(
        f"\n{_plural(len(selection.to_convert))} to convert, "
        f"{len(selection.skipped)} skipped, {len(selection.unread)} failed"
    )


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="convert_individual_licenses", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument(
        "--apply", action="store_true", help="Convert them; without it nothing changes"
    )
    parser.add_argument(
        "--yes", action="store_true", help="With --apply, skip the confirmation"
    )
    parser.add_argument(
        "--include-sold-after-decision",
        action="store_true",
        help=(
            "Also convert licenses sold since 1 Nov 2026, which ADR 0080 leaves to "
            "its open question q"
        ),
    )
    parser.add_argument(
        "--mark-notice-sent",
        nargs=2,
        metavar=("LICENSE_ID", "DAY"),
        help=(
            "Record that a run mailed this license's notice on DAY (YYYY-MM-DD) but "
            "could not record it, every other key kept; nothing else is done"
        ),
    )
    args = parser.parse_args(argv)
    if args.yes and not args.apply:
        parser.error("--yes goes with --apply")
    if args.mark_notice_sent is not None:
        if args.apply or args.include_sold_after_decision:
            parser.error("--mark-notice-sent goes alone")
        license_id, day = args.mark_notice_sent
        try:
            sent_on = date.fromisoformat(day)
        except ValueError:
            parser.error(f"--mark-notice-sent takes the day as YYYY-MM-DD, not {day}")
        return await _mark(license_id, sent_on)

    refusal = _refusal(apply=args.apply)
    if refusal is not None:
        print(f"error: {refusal}", file=sys.stderr)
        return 2

    individual_policy = str(config.KEYGEN_POLICY_INDIVIDUAL)
    try:
        business = await checked_business_policy(
            individual=individual_policy, business=str(config.KEYGEN_POLICY_BUSINESS)
        )
    except PolicyMismatchError as mismatch:
        print(f"error: {mismatch}", file=sys.stderr)
        return 2
    except (httpx2.HTTPError, RuntimeError, ValueError) as error:
        # ValueError: a body that is not JSON, as a proxy's page.
        print(f"error: could not read the policies in Keygen: {error}", file=sys.stderr)
        return 1
    print(
        f"to       {business.id}  {business.name}, which keeps each license's "
        "expiry when it moves (KEEP_EXPIRY)\n"
    )

    stripe_client = get_stripe_client()
    try:
        selection = await select_licenses(
            individual_policy=individual_policy,
            stripe_client=stripe_client,
            now=datetime.now(UTC),
            include_sold_after_decision=args.include_sold_after_decision,
        )
    except (httpx2.HTTPError, RuntimeError, ValueError) as error:
        print(f"error: could not list the licenses in Keygen: {error}", file=sys.stderr)
        return 1
    _print_selection(selection)
    unread = len(selection.unread)
    count = len(selection.to_convert)

    if not count:
        print("Nothing to convert.")
        return 1 if unread else 0
    if not args.apply:
        print("Nothing was changed; run again with --apply to convert them.")
        return 1 if unread else 0
    if not args.yes and input(
        f"\nConvert {_plural(count)} to Business Solo and mail each its notice? [y/N] "
    ).strip().lower() not in {"y", "yes"}:
        print("aborted")
        return 1

    print()
    now = datetime.now(UTC)
    failed = 0
    for candidate in selection.to_convert:
        line = _ProgressLine(candidate.record.keygen_license_id)
        outcome = await convert_license(
            candidate,
            business_policy=business.id,
            stripe_client=stripe_client,
            now=now,
            on_step=line.add,
        )
        line.end(outcome.failure)
        if outcome.failure is not None:
            failed += 1

    print(f"\n{count - failed} of {_plural(count)} converted, {failed} failed")
    return 1 if failed or unread else 0


async def _mark(license_id: str, sent_on: date) -> int:
    """``--mark-notice-sent``: Keygen alone, since nothing else is read or written."""
    try:
        refusal = await mark_notice_sent(license_id, sent_on)
    except (httpx2.HTTPError, RuntimeError, ValueError) as error:
        refusal = f"could not reach Keygen: {error}"
    if refusal is not None:
        print(f"error: {refusal}", file=sys.stderr)
        return 1
    print(f"{license_id}: notice recorded as sent on {sent_on.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
