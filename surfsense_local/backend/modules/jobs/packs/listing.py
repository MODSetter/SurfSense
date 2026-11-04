"""The installed packs as the Jobs screen lists them: each job, whether it may run here, and if
not, why and by which code."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.jobs.packs.access import LockCode, job_access
from modules.jobs.packs.installed import installed_packs


class JobInfo(BaseModel):
    key: str
    name: str
    description: str
    # The licence entitlement that unlocks it, for a paid pack's job.
    entitlement: str | None
    unlocked: bool
    locked_reason: str
    locked_code: LockCode | None


class PackInfo(BaseModel):
    id: str
    version: str
    name: str
    publisher: str
    access: str
    # Whether any of its jobs may run, and else why its first may not.
    unlocked: bool
    locked_reason: str
    locked_code: LockCode | None
    jobs: list[JobInfo]


def pack_listing(session: Session) -> list[PackInfo]:
    # Every pack is hashed before the session reads the licence, so no lock waits on it.
    packs = installed_packs()
    found = []
    for pack in packs:
        jobs = [
            (job, job_access(session, pack.manifest, job)) for job in pack.manifest.jobs
        ]
        unlocked = any(access.allowed for _, access in jobs)
        first = jobs[0][1]
        found.append(
            PackInfo(
                id=pack.manifest.id,
                version=pack.manifest.version,
                name=pack.manifest.name,
                publisher=pack.manifest.publisher,
                access=pack.manifest.access,
                unlocked=unlocked,
                locked_reason="" if unlocked else first.reason,
                locked_code=None if unlocked else first.code,
                jobs=[
                    JobInfo(
                        key=job.key,
                        name=job.name,
                        description=job.description,
                        entitlement=job.entitlement,
                        unlocked=access.allowed,
                        locked_reason=access.reason,
                        locked_code=access.code,
                    )
                    for job, access in jobs
                ],
            )
        )
    return found
