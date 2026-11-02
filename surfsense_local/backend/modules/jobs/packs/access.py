"""Whether a pack's jobs may run here: free ones always, paid ones on a Business licence.

No Business licence is issued yet, so a paid pack also runs under the developer
switch. Like every check in the app this is honesty, not enforcement: delivery
by the licence server and the pack's terms are what hold (ADR 0067).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.jobs.packs.manifest import PackManifest
from modules.license.service import status

DEV_SWITCH = "SURFSENSE_LOCAL_JOBS_UNLOCKED"
BUSINESS_PLANS = ("business",)


@dataclass(frozen=True)
class Access:
    allowed: bool
    reason: str  # the sentence the user reads when not allowed


def pack_access(session: Session, manifest: PackManifest) -> Access:
    if manifest.access == "free":
        return Access(True, "")
    if os.environ.get(DEV_SWITCH) == "1":
        return Access(True, "")
    license_status = status(session)
    if license_status.state == "active" and license_status.plan in BUSINESS_PLANS:
        return Access(True, "")
    return Access(
        False,
        f"{manifest.name} needs a SurfSense Business licence, or its 14-day trial.",
    )
