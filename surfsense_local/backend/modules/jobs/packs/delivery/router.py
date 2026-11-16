"""Getting a licence's job packs: downloaded from SurfSense's licence server, or imported from a
pack file, for a computer that cannot reach it."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact_fresh
from modules.jobs.packs.delivery.acceptance import accept_imported
from modules.jobs.packs.delivery.deliver import DeliveryRefusedError, deliver_packs
from modules.jobs.packs.delivery.outcomes import PackOutcome, default_message
from modules.jobs.packs.delivery.uploaded_pack import received_pack
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.jobs.packs.listing import PackInfo, pack_listing
from modules.jobs.packs.manifest import ENTITLEMENT, PackRefusedError
from modules.jobs.runs.in_flight import pack_in_use

router = APIRouter(tags=["jobs"])

# A licence's job code, as contract 6 names one: the only kind a request carries.
Entitlement = Annotated[str, StringConstraints(pattern=ENTITLEMENT.pattern)]

# Refusals the user resolves without another file: wait for the run, or import a newer one.
_CONFLICTS = frozenset({"PACK_OLDER", "PACK_IN_USE", "PACK_VERSION_TAKEN"})


class PackDownload(BaseModel):
    """The jobs to download, by code; left out, every job the licence includes."""

    entitlements: list[Entitlement] | None = Field(default=None, max_length=32)


class DeliveryRead(BaseModel):
    outcomes: list[PackOutcome]
    packs: list[PackInfo]


@router.post(
    "/job-packs/download",
    response_model=DeliveryRead,
    summary="Download the licence's job packs from SurfSense's licence server",
)
async def download(
    request: Request, payload: PackDownload | None = None
) -> DeliveryRead:
    """Every code's outcome is in the answer, failed ones too, a code held back by a run
    among them, which is checked again once the run ends. Only a request that can send
    nothing is refused: no job to ask for, or the licence server's host off in Settings >
    Network, raised after the plan's commit so Settings lists the host. The host is asked
    for even when a run holds every code back, as the check made once the run ends never
    asks, though sending nothing stamps no call there; a licence code no request may carry
    is an unknown job, and asks for no host."""
    sessions = request.app.state.session_factory
    try:
        delivery = await deliver_packs(
            sessions,
            payload.entitlements if payload is not None else None,
            person_asked=True,
        )
    except DeliveryRefusedError as refused:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": refused.code, "message": refused.message},
        ) from refused
    if delivery.refusal is not None:
        raise delivery.refusal
    return DeliveryRead(
        outcomes=list(delivery.outcomes),
        packs=await transact_fresh(sessions, pack_listing),
    )


@router.post(
    "/job-packs/import",
    response_model=list[PackInfo],
    summary="Import a job pack file",
)
def import_pack(file: UploadFile, session: SessionDep) -> list[PackInfo]:
    """The same signed pack again, or a newer version; never an older one."""
    name = Path(file.filename or "").name or "This file"
    try:
        received = received_pack(file, packs_dir())
        try:
            install_pack(
                received,
                packs_dir(),
                accept=accept_imported(lambda pack_id: _in_use(session, pack_id)),
            )
        finally:
            with suppress(OSError):
                received.unlink(missing_ok=True)
    except PackRefusedError as refused:
        raise _refused(refused, name) from refused
    except OSError as unwritten:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"code": "PACK_NOT_WRITTEN", "message": default_message("not_written")},
        ) from unwritten
    return pack_listing(session)


def _in_use(session: Session, pack_id: str) -> bool:
    """Committed at once, so the write lock is let go before any file moves."""
    used = pack_in_use(session, pack_id)
    session.commit()
    return used


def _refused(refused: PackRefusedError, name: str) -> HTTPException:
    if refused.code in _CONFLICTS:
        status_code = status.HTTP_409_CONFLICT
    elif refused.code == "PACK_TOO_LARGE":
        status_code = status.HTTP_413_CONTENT_TOO_LARGE
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    # Named for the file the user chose, never for the scratch copy it was read from.
    message = (
        f"{name} is not a SurfSense job pack."
        if refused.code == "NOT_A_PACK"
        else refused.message
    )
    return HTTPException(status_code, {"code": refused.code, "message": message})
