"""Job packs on this computer, the firm's settings for their jobs, and the runs of those jobs.

A pack installs from a folder or a .zip on this computer, the way a developer or the
licence server's download hands it over; a run starts from a workbook and its sources.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, StrictBool

from api.dependencies import SessionDep
from modules.artifacts.models import Artifact
from modules.embedding.dependencies import EMBEDDER_CHOSEN
from modules.jobs.packs.access import job_access
from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import find_job, installed_packs, packs_dir
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.runs.confirm import confirm_suggestions
from modules.jobs.runs.record import job_run_of
from modules.jobs.runs.start import JobRunRefusedError, start_job_run
from modules.jobs.settings.service import (
    ChosenSettings,
    JobSettingsRefusedError,
    job_settings,
    save_job_settings,
)
from modules.jobs.workbook_rows.config import JobConfig, load_config
from modules.llm.model_route.schemas import ModelRef

router = APIRouter(tags=["jobs"])


class PackInstall(BaseModel):
    path: str


class JobInfo(BaseModel):
    key: str
    name: str
    description: str
    # The licence entitlement that unlocks it, for a paid pack's job.
    entitlement: str | None
    unlocked: bool
    locked_reason: str


class PackInfo(BaseModel):
    id: str
    version: str
    name: str
    publisher: str
    access: str
    # Whether any of its jobs may run, and else why its first may not.
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


class JobSettingInfo(BaseModel):
    key: str
    label: str
    description: str
    default: bool
    value: bool


class JobSettingsRead(BaseModel):
    job: str
    settings: list[JobSettingInfo]
    # The model that makes the second checks; null checks on the answering model.
    checker: ModelRef | None


class JobSettingsWrite(BaseModel):
    """The whole of a job's settings: one left out is set to its default."""

    settings: dict[str, StrictBool] = {}
    checker: ModelRef | None = None


class SuggestionCell(BaseModel):
    sheet: str
    cell: str


class SuggestionsConfirm(BaseModel):
    """The answer cells whose suggestions to confirm; left out, every one not yet confirmed."""

    cells: list[SuggestionCell] | None = None


@router.get(
    "/job-packs", response_model=list[PackInfo], summary="List installed job packs"
)
def list_packs(session: SessionDep) -> list[PackInfo]:
    found = []
    for pack in installed_packs():
        jobs = [
            (job, job_access(session, pack.manifest, job)) for job in pack.manifest.jobs
        ]
        unlocked = any(access.allowed for _, access in jobs)
        found.append(
            PackInfo(
                id=pack.manifest.id,
                version=pack.manifest.version,
                name=pack.manifest.name,
                publisher=pack.manifest.publisher,
                access=pack.manifest.access,
                unlocked=unlocked,
                locked_reason="" if unlocked else jobs[0][1].reason,
                jobs=[
                    JobInfo(
                        key=job.key,
                        name=job.name,
                        description=job.description,
                        entitlement=job.entitlement,
                        unlocked=access.allowed,
                        locked_reason=access.reason,
                    )
                    for job, access in jobs
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


@router.get(
    "/job-packs/jobs/{job}/settings",
    response_model=JobSettingsRead,
    summary="Read the firm's settings for a job",
)
def read_settings(job: str, session: SessionDep) -> JobSettingsRead:
    config = _job_config(job)
    return _settings_read(job, config, job_settings(session, job, config))


@router.put(
    "/job-packs/jobs/{job}/settings",
    response_model=JobSettingsRead,
    summary="Set the firm's settings for a job, for every run that starts after",
)
def write_settings(
    job: str, payload: JobSettingsWrite, session: SessionDep
) -> JobSettingsRead:
    config = _job_config(job)
    try:
        chosen = save_job_settings(
            session, job, config, dict(payload.settings), payload.checker
        )
    except JobSettingsRefusedError as refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "BAD_JOB_SETTINGS", "message": str(refused)},
        ) from refused
    return _settings_read(job, config, chosen)


def _job_config(job: str) -> JobConfig:
    found = find_job(job)
    if found is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": f'No installed pack has a job "{job}".'},
        )
    pack, pack_job = found
    try:
        return load_config(pack.path(pack_job.config))
    except PackRefusedError as refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": refused.code, "message": refused.message},
        ) from refused


def _settings_read(
    job: str, config: JobConfig, chosen: ChosenSettings
) -> JobSettingsRead:
    return JobSettingsRead(
        job=job,
        settings=[
            JobSettingInfo(
                key=s.key,
                label=s.label,
                description=s.description,
                default=s.default,
                value=chosen.values[s.key],
            )
            for s in config.settings
        ],
        checker=chosen.checker,
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


@router.post(
    "/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm",
    dependencies=[EMBEDDER_CHOSEN],
    response_model=JobRunStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirm a run's suggested answers, as the next version of its revised copy",
)
def confirm(
    workspace_id: int,
    artifact_id: int,
    payload: SuggestionsConfirm,
    session: SessionDep,
) -> JobRunStarted:
    cells = (
        None if payload.cells is None else [(c.sheet, c.cell) for c in payload.cells]
    )
    try:
        made = confirm_suggestions(session, workspace_id, artifact_id, cells)
    except JobRunRefusedError as refused:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "JOB_RUN_REFUSED", "message": str(refused)},
        ) from refused
    return JobRunStarted(artifact_id=made.id)
