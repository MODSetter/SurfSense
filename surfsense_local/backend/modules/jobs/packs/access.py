"""Whether a pack's job may run here: a free pack's always, a paid pack's on a licence that
carries the job's entitlement, as every Business licence and the Business trial do (ADR 0080).

The licence's own expiry is the end of the period paid for plus 30 days, which is the grace
already, so the app adds none. The developer switch runs paid jobs without a licence. Like
every check in the app this is honesty, not enforcement: delivery by the licence server and
the pack's terms are what hold (ADR 0067).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from modules.jobs.packs.manifest import PackJob, PackManifest
from modules.license.service import LicenseStatus, status

DEV_SWITCH = "SURFSENSE_LOCAL_JOBS_UNLOCKED"

# Why a job is locked, for a screen to offer the step that unlocks it: no licence, one without
# the job, one that ended, a clock behind one already seen, or a job no licence can unlock.
LockCode = Literal["none", "not_included", "expired", "clock", "no_entitlement"]


@dataclass(frozen=True)
class Access:
    allowed: bool
    reason: str  # the sentence the user reads when not allowed
    code: LockCode | None = None  # None when allowed


def job_access(session: Session, manifest: PackManifest, job: PackJob) -> Access:
    """The one check a run passes when it starts and again when the worker works it out, so
    a retried run is checked too; the pack listing says what it would answer."""
    if manifest.access == "free" or os.environ.get(DEV_SWITCH) == "1":
        return Access(True, "")
    if job.entitlement is None:
        return Access(
            False,
            f"{job.name} names no licence entitlement, so no licence unlocks it.",
            "no_entitlement",
        )
    held = status(session)
    carried = job.entitlement in entitlements(held)
    if held.state == "active" and carried:
        return Access(True, "")
    code, reason = _refusal(held, job.name, carried)
    return Access(False, reason, code)


def entitlements(held: LicenseStatus) -> frozenset[str]:
    """The entitlement codes a licence carries, from its `metadata.jobs`; none on a licence
    without jobs."""
    jobs: str | Iterable[str] | None = getattr(held, "jobs", None)
    if isinstance(jobs, str):
        jobs = jobs.split(",")
    return frozenset(code.strip() for code in jobs or () if code and code.strip())


def _refusal(held: LicenseStatus, name: str, carried: bool) -> tuple[LockCode, str]:
    """Why the job cannot run, with the step that would let it: a licence that never carries the
    job is not told to renew, since renewing it would not unlock the job."""
    if held.state == "none":
        return (
            "none",
            f"{name} needs a SurfSense Business licence, or its 14-day trial.",
        )
    if not carried:
        return "not_included", (
            f"Your SurfSense licence does not include {name}: it comes with a Business "
            "licence, or its 14-day trial."
        )
    if held.state == "license_expired":
        return "expired", (
            f"Your SurfSense licence has expired, so {name} cannot run. Renew it, or import "
            "its newer file in Settings."
        )
    return "clock", (
        f"This computer's clock is behind a time your licence was already seen at, so "
        f"{name} cannot run until the clock is right."
    )
