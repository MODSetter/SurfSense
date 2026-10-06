"""The Office support state Settings shows, read from disk and the running install."""

from modules.egress.service import HOST_PREFIX
from modules.runtime_packs.office import pin, records
from modules.runtime_packs.office.detect import find_installed
from modules.runtime_packs.office.install import OfficeInstaller
from modules.runtime_packs.office.runtime import OfficeRuntime, office_runtime
from modules.runtime_packs.office.schemas import (
    OfficeDetected,
    OfficeOffer,
    OfficeProblem,
    OfficeProgress,
    OfficeStatusRead,
)

DESTINATION = f"{HOST_PREFIX}{pin.HOST}"


def office_status(installer: OfficeInstaller) -> OfficeStatusRead:
    activity = installer.activity
    runtime = office_runtime()
    found = find_installed()
    status = OfficeStatusRead(
        state="not_installed",
        version=None,
        path=None,
        progress=None,
        error=None,
        offer=_offer(installer),
        detected=None
        if found is None
        else OfficeDetected(
            path=str(found.root),
            branch=found.branch,
            usable=found.refusal is None,
            refusal=found.refusal,
        ),
    )
    if activity.phase is not None:
        status.state = activity.phase
        status.progress = OfficeProgress(
            completed=activity.completed, total=activity.total
        )
    elif isinstance(runtime, OfficeRuntime):
        status.version = runtime.version
        if runtime.source == "pack":
            status.state = "installed"
        else:
            status.state = "using_installed"
            status.path = records.read_confirmed().root
    elif activity.error is not None:
        status.state = "error"
        status.error = OfficeProblem(**activity.error)
    elif (confirmed := records.read_confirmed()) is not None:
        # Confirmed once, refused now: moved to an ended branch, or uninstalled.
        status.state = "error"
        status.path = confirmed.root
        status.error = OfficeProblem(
            code=f"installed_{runtime.reason}",
            message="the confirmed LibreOffice can no longer be used",
        )
    return status


def _offer(installer: OfficeInstaller) -> OfficeOffer | None:
    file = installer.file
    if file is None:
        return None
    return OfficeOffer(
        version=file.version, size=file.size, host=pin.HOST, destination=DESTINATION
    )
