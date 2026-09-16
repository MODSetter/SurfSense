"""What a license is, and the metadata keys Keygen holds it under.

There is no license table. Stripe and Keygen are the system of record, and
every lookup is a filter over Keygen license ``metadata``. Nothing in this
slice takes a database session or touches Postgres.

Spec: ``plans/community-local/portal/01-license-routes.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.license.keygen import LicensePlan

LicenseSource = Literal["stripe", "trial", "enterprise"]
PAID_STATUSES = {"paid", "no_payment_required"}

# Keygen camelCases metadata keys in filter queries, so these are the spellings
# both writes and lookups must use.
META_EMAIL = "email"
META_PLAN = "plan"
META_CUSTOMER = "stripeCustomerId"
META_SESSION = "checkoutSessionId"
# Trials carry a second index. ``email`` is the address as typed, because that
# is where mail goes and what resend looks up; ``trialKey`` is the folded form
# the one-trial-per-person check filters on. Storing only the folded form would
# misdirect delivery, and storing only the typed form would let a tagged
# address claim a trial the fold could never find again.
META_TRIAL_KEY = "trialKey"


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


@dataclass(frozen=True, slots=True)
class LicenseRecord:
    """A license as Keygen holds it, for an operator to eyeball before editing."""

    keygen_license_id: str
    metadata: dict[str, str]
    max_users: int | None = None
    expiry: str | None = None
