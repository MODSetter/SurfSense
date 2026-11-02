"""Job packs on this computer and the runs of their jobs.

A pack installs from a folder or a .zip on this computer, the way a developer or the
licence server's download hands it over; a run starts from a workbook and its sources.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.artifacts.models import Artifact
from modules.jobs.packs.access import pack_access
from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import installed_packs, packs_dir
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.runs.record import job_run_of
from modules.jobs.runs.start import JobRunRefusedError, start_job_run

router = APIRouter(tags=["jobs"])


class PackInstall(BaseModel):
    path: str


class JobInfo(BaseModel):
    key: str
    name: str
    description: str


class PackInfo(BaseModel):
    id: str
    version: str
    name: str
    publisher: str
    access: str
    unlocked: bool
    locked_reason: str
    jobs: list[JobInfo]


class JobRunStart(BaseModel):
    job: str
    document_id: int
    source_ids: list[int]
    chat_thread_id: int | None = None


class JobRunStarted(BaseModel):
    artifact_id: int


@router.get(
    "/job-packs", response_model=list[PackInfo], summary="List installed job packs"
)
def list_packs(session: SessionDep) -> list[PackInfo]:
    found = []
    for pack in installed_packs():
        access = pack_access(session, pack.manifest)
        found.append(
            PackInfo(
                id=pack.manifest.id,
                version=pack.manifest.version,
                name=pack.manifest.name,
                publisher=pack.manifest.publisher,
                access=pack.manifest.access,
                unlocked=access.allowed,
                locked_reason=access.reason,
                jobs=[
                    JobInfo(key=j.key, name=j.name, description=j.description)
                    for j in pack.manifest.jobs
                ],
            )
        )
    return found


@router.post(
    "/job-packs/install",
    response_model=list[PackInfo],
    summary="Install a job pack from a folder or .zip",
)
def install(payload: PackInstall, session: SessionDep) -> list[PackInfo]:
    source = Path(payload.path)
    if not source.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": f"{source} does not exist."},
        )
    try:
        install_pack(source, packs_dir())
    except PackRefusedError as refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": refused.code, "message": refused.message},
        ) from refused
    return list_packs(session)


@router.delete(
    "/job-packs/{pack_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a job pack",
)
def remove(pack_id: str) -> None:
    if not remove_pack(pack_id, packs_dir()):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": f"No pack {pack_id}."},
        )


@router.post(
    "/workspaces/{workspace_id}/job-runs",
    response_model=JobRunStarted,
    status_code=status.HTTP_201_CREATED,
    summary="Run a job on a workbook and its sources",
)
def start(
    workspace_id: int, payload: JobRunStart, session: SessionDep
) -> JobRunStarted:
    try:
        artifact = start_job_run(
            session,
            workspace_id,
            job=payload.job,
            workbook_document_id=payload.document_id,
            source_document_ids=payload.source_ids,
            chat_thread_id=payload.chat_thread_id,
        )
    except JobRunRefusedError as refused:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "JOB_RUN_REFUSED", "message": str(refused)},
        ) from refused
    return JobRunStarted(artifact_id=artifact.id)


@router.get(
    "/workspaces/{workspace_id}/job-runs/{artifact_id}",
    summary="Read a job run's status and report",
)
def read_run(workspace_id: int, artifact_id: int, session: SessionDep) -> dict:
    artifact = session.get(Artifact, artifact_id)
    run = job_run_of(artifact.artifact_metadata) if artifact is not None else None
    if artifact is None or artifact.workspace_id != workspace_id or run is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": "No such job run."},
        )
    document = artifact.document
    return {
        "artifact_id": artifact.id,
        "status": document.status.value,
        "error": document.error_message,
        "job": run["job"],
        "pack": f"{run['pack_id']} {run['pack_version']}",
        "report": run.get("report"),
    }
