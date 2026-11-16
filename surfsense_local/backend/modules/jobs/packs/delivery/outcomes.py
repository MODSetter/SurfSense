"""What one job code's download came to, in the codes and sentences the Jobs screen reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OutcomeCode = Literal[
    "installed",
    "current",
    "deferred",
    "job_not_included",
    "pack_not_covered",
    "license_not_valid",
    "license_not_found",
    "license_outdated",
    "needs_newer_app",
    "unknown_job",
    "rate_limited",
    "unavailable",
    "refused",
    "not_written",
]


@dataclass(frozen=True)
class PackOutcome:
    entitlement: str
    outcome: OutcomeCode
    message: str
    # The version installed now, where the outcome names one: the new one, or the one that
    # stays because it is current, a run held it, or this computer's license file is older.
    # A deferral for a job no installed pack has names the version a run of the job reads,
    # or none when the run is of another job of the pack.
    version: str | None = None
    # The server's `detail.code`, or the code a downloaded pack was refused with.
    detail: str | None = None


# `installed` names the pack and `refused` gives the check's own sentence, at the call site.
_MESSAGES: dict[str, str] = {
    "current": "The newest version of this job is installed.",
    "deferred": (
        "A run of this job was under way, so any newer version waits until the run ends."
    ),
    "job_not_included": "Your license does not include this job.",
    "pack_not_covered": (
        "This job comes only in a pack with a job your license does not include. "
        "Contact support."
    ),
    "license_not_valid": (
        "SurfSense's license server will not send jobs for this license. "
        "Contact support."
    ),
    "license_not_found": "SurfSense's license server has no license with this key.",
    "license_outdated": (
        "Your license has changed on SurfSense's license server. Check for renewal, "
        "then download the job again."
    ),
    "needs_newer_app": (
        "This job needs a newer SurfSense. Update the app, then download it again."
    ),
    "unknown_job": "SurfSense's license server does not offer this job.",
    "rate_limited": "This license asked for jobs too often; try again in an hour.",
    "unavailable": (
        "SurfSense's license server could not send the job; try again later."
    ),
    "not_written": "The pack could not be written to this computer's disk.",
}


# A download held back for a job no installed pack has: the newer version of a pack that adds
# it waits for a run of another of that pack's jobs.
DEFERRED_FOR_ANOTHER_JOB = (
    "A run of another job in the same pack was under way, so this job waits until the run "
    "ends."
)


def default_message(outcome: OutcomeCode) -> str:
    return _MESSAGES[outcome]
