"""Office support in Settings: its state, turning it on, using an installed LibreOffice, removing it.

Nothing downloads unless the user turns it on, and only once they allowed the
download host (egress consent per host, ADR 0027).
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.runtime_packs.office.confirm import ConfirmRefusedError, confirm_installed
from modules.runtime_packs.office.install import OfficeInstaller, OfficeInUseError
from modules.runtime_packs.office.pin import FILES
from modules.runtime_packs.office.platform_key import this_platform
from modules.runtime_packs.office.runtime import OfficeRuntime, office_runtime
from modules.runtime_packs.office.schemas import OfficeStatusRead
from modules.runtime_packs.office.status import DESTINATION, office_status

router = APIRouter(prefix="/runtime-packs/office", tags=["runtime-packs"])

# A frame this often even when nothing changed keeps the connection alive.
_HEARTBEAT_SECONDS = 15


def get_office_installer(request: Request) -> OfficeInstaller:
    """One per app; made on first use so a test can put its own on app.state first."""
    installer = getattr(request.app.state, "office_installer", None)
    if installer is None:
        installer = OfficeInstaller(FILES.get(this_platform() or ""))
        request.app.state.office_installer = installer
    return installer


InstallerDep = Annotated[OfficeInstaller, Depends(get_office_installer)]


def _refuse(code: int, problem: str, message: str) -> HTTPException:
    return HTTPException(code, {"code": problem, "message": message})


@router.get("", response_model=OfficeStatusRead, summary="Office support's state")
def read_office(installer: InstallerDep) -> OfficeStatusRead:
    return office_status(installer)


@router.get(
    "/events",
    summary="Office support's state as NDJSON: now, then again on each change",
)
async def follow_office(installer: InstallerDep) -> StreamingResponse:
    async def frames() -> AsyncIterator[bytes]:
        changed = installer.subscribe()
        try:
            while True:
                changed.clear()
                read = await asyncio.to_thread(office_status, installer)
                yield (read.model_dump_json() + "\n").encode()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(changed.wait(), _HEARTBEAT_SECONDS)
        finally:
            installer.unsubscribe(changed)

    return StreamingResponse(
        frames(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/install",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OfficeStatusRead,
    summary="Download and unpack TDF's LibreOffice; needs its host allowed first",
)
async def install_office(
    installer: InstallerDep, session: SessionDep
) -> OfficeStatusRead:
    if installer.file is None:
        raise _refuse(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_platform",
            "no LibreOffice build is pinned for this platform",
        )
    # 403 egress_disabled names the host, so the interface can ask for it.
    await transact(session, egress.require, DESTINATION)
    # A reinstall would replace the folder a LibreOffice run may be using.
    runtime = await asyncio.to_thread(office_runtime)
    if isinstance(runtime, OfficeRuntime) and runtime.source == "pack":
        raise _refuse(
            status.HTTP_409_CONFLICT,
            "already_installed",
            "Office support is installed; remove it first",
        )
    # Checked after the last await, so two requests cannot both start one.
    if installer.running():
        raise _refuse(
            status.HTTP_409_CONFLICT, "already_running", "Office support is installing"
        )
    installer.start()
    return office_status(installer)


@router.post(
    "/use-installed",
    response_model=OfficeStatusRead,
    summary="Use the LibreOffice found at a fixed install path, after a check run",
)
async def use_installed_office(installer: InstallerDep) -> OfficeStatusRead:
    if installer.running():
        raise _refuse(
            status.HTTP_409_CONFLICT, "already_running", "Office support is installing"
        )
    try:
        await asyncio.to_thread(
            confirm_installed,
            smoke=installer.smoke,
            version_of=installer.version_of,
        )
    except ConfirmRefusedError as refused:
        code = (
            status.HTTP_404_NOT_FOUND
            if refused.code == "not_found"
            else status.HTTP_409_CONFLICT
        )
        raise _refuse(code, refused.code, str(refused)) from refused
    return office_status(installer)


@router.delete(
    "",
    response_model=OfficeStatusRead,
    summary="Cancel the install, or stop using Office support and delete the pack",
)
async def remove_office(installer: InstallerDep) -> OfficeStatusRead:
    if not await installer.cancel():
        try:
            await asyncio.to_thread(installer.remove)
        except OfficeInUseError as in_use:
            raise _refuse(
                status.HTTP_409_CONFLICT,
                "in_use",
                "LibreOffice is running; try again when the current job ends",
            ) from in_use
    return office_status(installer)
