"""Download the jobs a licence includes from SurfSense's licence server and install each pack
that passes, one code at a time (contract 6, consumer rules 1, 2, 5 and 7).

A code a run of its pack holds back is recorded (`held_back.py`), so the schedule checks it
once more when the run ends. That check is background work, which never asks to reach the
licence server, so a person's request asks for the host whenever a code would be asked for,
now or once a run ends; the app's own checks ask nothing, and need the host only for a code
they would send now. Only a code sent now stamps the host's last call in Settings > Network.
Every stretch of database work is a session of its own on a worker thread, so a cancel at
any await, as when the API stops, never closes a session under a thread; nothing holds a
transaction across a request to the server.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact_fresh
from modules.egress.service import EgressDeniedError, refused_named_host
from modules.jobs.packs.delivery.acceptance import accept_delivered
from modules.jobs.packs.delivery.held_back import HELD_BACK
from modules.jobs.packs.delivery.outcomes import (
    DEFERRED_FOR_ANOTHER_JOB,
    PackOutcome,
    default_message,
)
from modules.jobs.packs.delivery.pack_request import Answered, request_pack
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs, packs_dir
from modules.jobs.packs.manifest import (
    ENTITLEMENT,
    PackManifest,
    PackRefusedError,
    version_key,
)
from modules.jobs.runs.in_flight import pack_in_use, version_in_use
from modules.license.license_key import license_key
from modules.license.renewal.license_server import license_server
from modules.license.service import status

# The consent question words itself by this when the host alone does not say, as for a
# firm's mirror: the same host also renews the licence.
PURPOSE = "job_packs"

logger = logging.getLogger(__name__)


class DeliveryRefusedError(Exception):
    """No job can be asked for, so nothing is sent: no licence, one not active, or one with no
    jobs."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Wanted:
    entitlement: str
    carried: bool  # whether the licence's jobs list it
    installed: PackManifest | None  # the newest installed pack with a job for it
    # That pack's id while a run of it is pending or processing, which holds the code back.
    held_by: str | None
    # Whether contract 6's request takes the code at all; a hand-issued licence may list
    # one it does not.
    sendable: bool = True


@dataclass(frozen=True)
class Plan:
    key: str = field(repr=False)
    held_jobs: frozenset[str]
    wanted: tuple[Wanted, ...]


@dataclass(frozen=True)
class Delivery:
    # The licence server's host, off in Settings > Network: nothing was sent.
    refusal: EgressDeniedError | None
    outcomes: tuple[PackOutcome, ...] = ()


async def deliver_packs(
    sessions: sessionmaker[Session],
    entitlements: list[str] | None = None,
    *,
    person_asked: bool = False,
) -> Delivery:
    """Each code's outcome, in order: `entitlements`, or every job the licence includes.
    Raises DeliveryRefusedError before anything is sent. A code a run held back is recorded
    for the schedule to check once more when the run ends; any other outcome ends that.

    `person_asked` is a person's own request, which needs the licence server's host for any
    code it could ask for, a code a run holds back among them, since the check made once
    the run ends never asks; without it, the host is needed only for a code sent now. Either
    way the host's last call is stamped only when a code is sent now."""
    server = license_server()
    planned = await transact_fresh(
        sessions, _planned, server, entitlements, person_asked
    )
    if isinstance(planned, EgressDeniedError):
        return Delivery(planned)
    outcomes = []
    for wanted in planned.wanted:
        outcome, held_by = await _delivered(sessions, server, planned, wanted)
        if held_by is None:
            HELD_BACK.release([wanted.entitlement])
        else:
            HELD_BACK.hold(wanted.entitlement, held_by)
        outcomes.append(outcome)
    return Delivery(None, tuple(outcomes))


def _planned(
    session: Session, server: str, entitlements: list[str] | None, person_asked: bool
) -> Plan | EgressDeniedError:
    """The plan, or the refusal, returned so the commit keeps a mirror's row for Settings."""
    # First, so hashing every installed pack holds no write lock.
    installed = [pack.manifest for pack in installed_packs()]
    key = license_key(session)
    if key is None:
        raise DeliveryRefusedError(
            "license_none", "No license is added, so there is no job to download."
        )
    held = status(session)
    if held.state != "active":
        raise DeliveryRefusedError(
            "license_not_active",
            "The license has ended, or this computer's clock is behind, so no job can "
            "be downloaded.",
        )
    if not held.jobs:
        raise DeliveryRefusedError(
            "license_no_jobs", "This license includes no jobs to download."
        )
    held_jobs = frozenset(held.jobs)
    wanted = []
    for code in dict.fromkeys(entitlements or held.jobs):
        if not ENTITLEMENT.fullmatch(code):
            # No pack has a job for it, and the server would refuse the request.
            wanted.append(Wanted(code, code in held_jobs, None, None, sendable=False))
            continue
        newest = _newest_with(installed, code)
        held_by = (
            newest.id
            if newest is not None and pack_in_use(session, newest.id)
            else None
        )
        wanted.append(Wanted(code, code in held_jobs, newest, held_by))
    # A code no run holds back is asked for now: the call Settings > Network stamps.
    sending = any(w.sendable and w.carried and w.held_by is None for w in wanted)
    # A person is asked even when a run holds every code back: the check made once the run
    # ends is the schedule's, which never asks, and would find the host off. Nothing is sent
    # now, so no call is stamped; that check stamps the one it makes.
    if sending or (person_asked and any(w.sendable and w.carried for w in wanted)):
        refused = refused_named_host(session, server, calling=sending)
        if refused is not None:
            refused.purpose = PURPOSE
            return refused
    return Plan(key, held_jobs, tuple(wanted))


def _newest_with(installed: list[PackManifest], code: str) -> PackManifest | None:
    holding = [p for p in installed if any(j.entitlement == code for j in p.jobs)]
    return max(holding, key=lambda pack: version_key(pack.version), default=None)


async def _delivered(
    sessions: sessionmaker[Session], server: str, plan: Plan, wanted: Wanted
) -> tuple[PackOutcome, str | None]:
    """The code's outcome, and the id of the pack whose run held it back, when one did."""
    code = wanted.entitlement
    installed = wanted.installed.version if wanted.installed is not None else None
    if not wanted.sendable:
        logger.info(
            "job code %r is not one the license server takes, so it is not asked for",
            code[:64],
        )
        return PackOutcome(code, "unknown_job", default_message("unknown_job")), None
    if not wanted.carried:
        return PackOutcome(
            code, "job_not_included", default_message("job_not_included")
        ), None
    if wanted.held_by is not None:
        # The runner reads the pack's files by path; the code is asked for once the run ends.
        # Only an installed pack with the job holds it back here, so the version is named.
        deferred = PackOutcome(code, "deferred", default_message("deferred"), installed)
        return deferred, wanted.held_by
    answer = await request_pack(server, plan.key, code, installed)
    if isinstance(answer, Answered):
        kept = installed if answer.outcome == "current" else None
        return PackOutcome(
            code, answer.outcome, answer.message, kept, answer.detail
        ), None
    return await run_in_threadpool(
        _install_downloaded, sessions, answer.path, code, plan.held_jobs, installed
    )


def _install_downloaded(
    sessions: sessionmaker[Session],
    path: Path,
    code: str,
    held_jobs: frozenset[str],
    installed: str | None,
) -> tuple[PackOutcome, str | None]:
    """Installs the downloaded zip, which goes afterwards whatever happened; beside the
    outcome, the id of the pack whose run held the install back, when one did."""
    held_by: list[str] = []
    offered: list[PackManifest] = []
    # When a run holds the pack back while no installed pack has the job: the version a run
    # of this job reads, as when its pack fails its checks since the run began, or None for
    # a run of another of the pack's jobs. Read in the session that found the run.
    run_versions: list[str | None] = []

    def in_use(pack_id: str) -> bool:
        """Read in a session of its own on the install's thread, ended before any file
        moves."""
        with sessions() as session:
            used = pack_in_use(session, pack_id)
            if used and installed is None:
                jobs = [job.key for job in offered[-1].jobs if job.entitlement == code]
                run_versions.append(version_in_use(session, pack_id, jobs))
        if used:
            held_by.append(pack_id)
        return used

    delivered = accept_delivered(code, held_jobs, in_use)

    def accept(new: PackManifest, verified: list[PackManifest]) -> None:
        # Kept before the rules look for a run, so the run is told apart by its job.
        offered.append(new)
        delivered(new, verified)

    try:
        manifest = install_pack(path, packs_dir(), accept=accept)
    except PackRefusedError as refused:
        if refused.code == "PACK_IN_USE" and run_versions:
            return _held_back_unlisted(code, run_versions[-1]), held_by[-1]
        return _refused(code, refused, installed), (held_by[-1] if held_by else None)
    except OSError as unwritten:
        logger.warning("job pack for %s not written: %s", code, unwritten)
        return PackOutcome(code, "not_written", default_message("not_written")), None
    finally:
        with suppress(OSError):
            path.unlink(missing_ok=True)
    return PackOutcome(
        code,
        "installed",
        f"{manifest.name} {manifest.version} is installed.",
        manifest.version,
    ), None


def _held_back_unlisted(code: str, run_version: str | None) -> PackOutcome:
    """A pack a run held back while no installed pack had the job; `run_version` is the
    version a run of this job reads, None when the run is of another job."""
    if run_version is None:
        # The run is of another job of the pack, whose newer version adds this one. The only
        # deferral without a version, which the Jobs screen reads as this case: every other
        # names the installed version, or the one a run of this job reads.
        return PackOutcome(code, "deferred", DEFERRED_FOR_ANOTHER_JOB)
    return PackOutcome(code, "deferred", default_message("deferred"), run_version)


def _refused(
    code: str, refused: PackRefusedError, installed: str | None
) -> PackOutcome:
    if refused.code == "PACK_NOT_NEWER":
        return PackOutcome(code, "current", default_message("current"), installed)
    if refused.code == "PACK_IN_USE":
        # An installed pack had the job: `_held_back_unlisted` takes the other case.
        return PackOutcome(code, "deferred", default_message("deferred"), installed)
    if refused.code == "NEEDS_NEWER_APP":
        return PackOutcome(code, "needs_newer_app", default_message("needs_newer_app"))
    if refused.code == "PACK_NOT_INCLUDED":
        # The server sends a pack only to a licence whose jobs, in its own record, list
        # every job in it: this computer's licence file is the older one.
        logger.info(
            "job pack for %s holds a job this computer's license file does not list",
            code,
        )
        return PackOutcome(
            code,
            "license_outdated",
            default_message("license_outdated"),
            installed,
            refused.code,
        )
    logger.warning("job pack for %s refused: %s", code, refused.message)
    # The check's own sentence would name the download's scratch file.
    message = (
        "The license server sent a file that is not a SurfSense job pack."
        if refused.code == "NOT_A_PACK"
        else refused.message
    )
    return PackOutcome(code, "refused", message, detail=refused.code)
