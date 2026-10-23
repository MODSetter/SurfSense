"""Trials grouped by the ISO week they were issued, joined to plugin use and payment."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .email_kind import EmailKind, email_kind
from .models import Purchase, Trial

ALL_WEEKS = "All"


@dataclass(frozen=True, slots=True)
class Cohort:
    label: str
    # The newest trial date it can hold, which decides whether a window is open.
    last_day: date
    trials: int
    company: int
    free_mail: int
    education: int
    # None when there was no plugin host data to read.
    seen_on_host: int | None
    days_to_first_call: tuple[int, ...]
    paid_within_30: int
    paid_within_60: int
    days_to_pay: tuple[int, ...]
    refunded: int


@dataclass(frozen=True, slots=True)
class _Outcome:
    trial: Trial
    kind: EmailKind
    days_to_first_call: int | None
    days_to_pay: int | None
    refunded: bool


def weekly_cohorts(
    trials: Iterable[Trial],
    purchases: Iterable[Purchase],
    first_seen: dict[str, date] | None,
) -> list[Cohort]:
    """One cohort per ISO week, oldest first, then one for every week together."""
    by_email = _purchases_by_email(purchases)
    by_week: dict[tuple[int, int], list[_Outcome]] = defaultdict(list)
    for trial in trials:
        year, week, _ = trial.created.isocalendar()
        by_week[(year, week)].append(_outcome(trial, by_email, first_seen))

    has_host = first_seen is not None
    cohorts = [
        _cohort(
            f"{year}-W{week:02d}",
            date.fromisocalendar(year, week, 7),
            outcomes,
            has_host,
        )
        for (year, week), outcomes in sorted(by_week.items())
    ]
    everyone = [outcome for outcomes in by_week.values() for outcome in outcomes]
    if everyone:
        newest = max(outcome.trial.created for outcome in everyone)
        cohorts.append(_cohort(ALL_WEEKS, newest, everyone, has_host))
    return cohorts


def _purchases_by_email(purchases: Iterable[Purchase]) -> dict[str, list[Purchase]]:
    index: dict[str, list[Purchase]] = defaultdict(list)
    for purchase in purchases:
        for email in purchase.folded_emails:
            index[email].append(purchase)
    return index


def _outcome(
    trial: Trial,
    by_email: dict[str, list[Purchase]],
    first_seen: dict[str, date] | None,
) -> _Outcome:
    # A purchase before the trial is not a conversion of it.
    later = [
        p for p in by_email.get(trial.folded_email, []) if p.paid_on >= trial.created
    ]
    purchase = min(later, key=lambda p: p.paid_on) if later else None
    seen = (first_seen or {}).get(trial.licence_id)
    return _Outcome(
        trial=trial,
        kind=email_kind(trial.folded_email),
        days_to_first_call=max(0, (seen - trial.created).days) if seen else None,
        days_to_pay=(purchase.paid_on - trial.created).days if purchase else None,
        refunded=bool(purchase and purchase.refunded),
    )


def _cohort(
    label: str, last_day: date, outcomes: list[_Outcome], has_host: bool
) -> Cohort:
    kinds = [outcome.kind for outcome in outcomes]
    first_calls = tuple(
        o.days_to_first_call for o in outcomes if o.days_to_first_call is not None
    )
    paid = tuple(o.days_to_pay for o in outcomes if o.days_to_pay is not None)
    return Cohort(
        label=label,
        last_day=last_day,
        trials=len(outcomes),
        company=kinds.count("company"),
        free_mail=kinds.count("free_mail"),
        education=kinds.count("education"),
        seen_on_host=len(first_calls) if has_host else None,
        days_to_first_call=first_calls,
        paid_within_30=sum(1 for days in paid if days <= 30),
        paid_within_60=sum(1 for days in paid if days <= 60),
        days_to_pay=paid,
        refunded=sum(1 for o in outcomes if o.refunded),
    )
