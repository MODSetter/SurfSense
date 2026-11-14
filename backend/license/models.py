"""What a license is, and the metadata keys Keygen holds it under.

There is no license table. Stripe and Keygen are the system of record, and
every lookup is a filter over Keygen license ``metadata``. Nothing in this
slice takes a database session or touches Postgres.

Spec: ``docs/architecture/license/portal.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from license.keygen import LicensePlan

LicenseSource = Literal["stripe", "trial", "enterprise"]
PAID_STATUSES = {"paid", "no_payment_required"}

# The one spelling of each key, for writes and lookups alike. Keygen ignores
# case, since it snake-cases keys, but a key with a different word finds nothing.
META_EMAIL = "email"
META_PLAN = "plan"
META_CUSTOMER = "stripeCustomerId"
META_SESSION = "checkoutSessionId"
# The subscription a license renews with. Licenses sold before it was written
# are found through their checkout session instead, and get it on renewal.
META_SUBSCRIPTION = "stripeSubscriptionId"
# Business only: the firm's name from the checkout's custom field, and the jobs.
META_FIRM = "firm"
META_JOBS = "jobs"
# Trials carry a second index. ``email`` is the address as typed, because that
# is where mail goes and what resend looks up; ``trialKey`` is the folded form
# the one-trial-per-person check filters on. Storing only the folded form would
# misdirect delivery, and storing only the typed form would let a tagged
# address claim a trial the fold could never find again.
META_TRIAL_KEY = "trialKey"
# An Individual license made Business Solo (scripts/convert_individual_licenses.py).
# ``convertedFrom`` has one value, so a filter finds a license a stopped run left
# half converted; the rest record the day, the expiry it had, and each later step.
META_CONVERTED_FROM = "convertedFrom"
META_CONVERTED_ON = "convertedOn"
META_EXPIRY_BEFORE_CONVERSION = "expiryBeforeConversion"
META_MOVED_TO_BUSINESS_ON = "movedToBusinessOn"
META_CONVERSION_NOTICE_SENT_ON = "conversionNoticeSentOn"


class LicenseIssueError(RuntimeError):
    """A checkout session that cannot be turned into a license."""


class TrialAlreadyClaimedError(RuntimeError):
    """This address has already taken its one trial."""


class LicenseNotFoundError(RuntimeError):
    """No license matches the identifier support supplied."""


@dataclass(frozen=True, slots=True)
class IssuedLicense:
    """One license as it exists for the duration of a request. Never persisted."""

    keygen_license_id: str
    certificate: str
    plan: LicensePlan
    email: str
    max_users: int | None = None
    firm: str | None = None
    # Non-empty for Business and the Business trial.
    jobs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LicenseRecord:
    """A license as Keygen holds it, for an operator to eyeball before editing."""

    keygen_license_id: str
    metadata: dict[str, str]
    max_users: int | None = None
    expiry: str | None = None
    policy: str | None = None
    status: str | None = None
    created: str | None = None
