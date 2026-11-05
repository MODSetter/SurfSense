"""The job plugins Business and its trial unlock, as Keygen entitlement codes.

One list for both carriers: the setup script attaches each code to the Business
policies, so Keygen can check it server side, and every Business license lists
them in ``metadata.jobs``, the copy the app reads offline from the file.
"""

from __future__ import annotations

from collections.abc import Mapping

from license.models import META_JOBS

# Every job is in Business (ADR 0080, open question a); a new one is added here
# and the setup script is run again.
JOBS: dict[str, str] = {
    "JOB_QUESTIONNAIRE": "Security questionnaire",
}


def jobs_metadata() -> str:
    """``metadata.jobs``: the codes, comma-separated, since metadata holds strings."""
    return ",".join(JOBS)


def jobs_of(metadata: Mapping[str, object]) -> tuple[str, ...]:
    """``metadata.jobs`` read as the app reads it (contract 1), so both sides list the same jobs."""
    raw = metadata.get(META_JOBS)
    if not isinstance(raw, str):
        return ()
    trimmed = (code.strip() for code in raw.split(","))
    return tuple(dict.fromkeys(code for code in trimmed if code))
