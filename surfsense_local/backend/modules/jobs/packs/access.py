"""Whether a pack's job may run here: a free pack's always, a paid pack's on a licence that
carries the job's entitlement, as every Business licence and the Business trial do (ADR 0079).

The licence's own expiry is the end of the period paid for plus 30 days, which is the grace
already, so the app adds none. The developer switch runs paid jobs without a licence. Like
every check in the app this is honesty, not enforcement: delivery by the licence server and
the pack's terms are what hold (ADR 0067).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.jobs.packs.manifest import PackJob, PackManifest
from modules.license.service import LicenseStatus, status

DEV_SWITCH = "SURFSENSE_LOCAL_JOBS_UNLOCKED"


@dataclass(frozen=True)
class Access:
    allowed: bool
    reason: str  # the sentence the user reads when not allowed


def job_access(session: Session, manifest: PackManifest, job: PackJob) -> Access:
    """The one check every run and every listing of a job goes through."""
    if manifest.access == "free" or os.environ.get(DEV_SWITCH) == "1":
        return Access(True, "")
    if job.entitlement is None:
        return Access(
            False, f"{job.name} names no licence entitlement, so no licence unlocks it."
        )
    held = status(session)
    if held.state == "active" and job.entitlement in entitlements(held):
        return Access(True, "")
    return Access(False, _refusal(held, job.name))


def entitlements(held: LicenseStatus) -> frozenset[str]:
    """The entitlement codes a licence carries, from its `metadata.jobs`: none until the licence
    module reads them, and none on a licence without jobs."""
    jobs: str | Iterable[str] | None = getattr(held, "jobs", None)
    if isinstance(jobs, str):
        jobs = jobs.split(",")
    return frozenset(code.strip() for code in jobs or () if code and code.strip())


def _refusal(held: LicenseStatus, name: str) -> str:
    if held.state == "license_expired":
        return (
            f"Your SurfSense licence has expired, so {name} cannot run. Renew it, or import "
            "its newer file in Settings."
        )
    if held.state == "clock_untrusted":
        return (
            f"This computer's clock is behind a time your licence was already seen at, so "
            f"{name} cannot run until the clock is right."
        )
    if held.state == "active":
        return (
            f"Your SurfSense licence does not include {name}: it comes with a Business "
            "licence, or its 14-day trial."
        )
    return f"{name} needs a SurfSense Business licence, or its 14-day trial."
