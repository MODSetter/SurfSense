"""Job packs on this computer, the firm's settings for their jobs, and the runs of those jobs.

A developer installs a pack from a folder or a .zip on this computer; a licence's packs come
from the licence server or a pack file (`packs/delivery/`). A run starts from a workbook and
its sources.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, StrictBool

from api.dependencies import SessionDep
from modules.embedding.dependencies import EMBEDDER_CHOSEN
from modules.jobs.packs.delivery.outcomes import default_message
from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import find_job, packs_dir
from modules.jobs.packs.listing import PackInfo, pack_listing
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.runners import runner_of
from modules.jobs.runs.confirm import confirm_suggestions
from modules.jobs.runs.run_read import (
    JobRunRead,
    JobRunSummary,
    run_read,
    run_summaries,
)
from modules.jobs.runs.start import JobRunRefusedError, start_job_run
from modules.jobs.settings.declared import DeclaresSettings
from modules.jobs.settings.service import (
    ChosenSettings,
    JobSettingsRefusedError,
    job_settings,
    save_job_settings,
)
from modules.llm.model_route.schemas import ModelRef

router = APIRouter(tags=["jobs"])


class PackInstall(BaseModel):
    path: str


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
    # Whether the job checks its answers a second time; a checker is used only when it does.
    checks: bool
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
    return pack_listing(session)


@router.post(
    "/job-packs/install",
    response_model=list[PackInfo],
    summary="Install a job pack from a folder or .zip",
)
def install(payload: PackInstall, session: SessionDep) -> list[PackInfo]:
    """For developers and live tests: any version installs, and other contents at an installed
    version replace it."""
    source = Path(payload.path)
    if not source.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": f"{source} does not exist."},
        )
    try:
        install_pack(source, packs_dir(), replace_same_version=True)
    except PackRefusedError as refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": refused.code, "message": refused.message},
        ) from refused
    except OSError as unwritten:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"code": "PACK_NOT_WRITTEN", "message": default_message("not_written")},
        ) from unwritten
    return pack_listing(session)


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


def _job_config(job: str) -> DeclaresSettings:
    found = find_job(job)
    if found is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": f'No installed pack has a job "{job}".'},
        )
    pack, pack_job = found
    try:
        return runner_of(pack_job).load_config(pack.path(pack_job.config))
    except PackRefusedError as refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": refused.code, "message": refused.message},
        ) from refused


def _settings_read(
    job: str, config: DeclaresSettings, chosen: ChosenSettings
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
        checks=config.checks,
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
            document_id=payload.document_id,
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
    "/workspaces/{workspace_id}/job-runs",
    response_model=list[JobRunSummary],
    summary="List a workspace's job runs, newest first",
)
def list_runs(
    workspace_id: int,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JobRunSummary]:
    return run_summaries(session, workspace_id, limit)


@router.get(
    "/workspaces/{workspace_id}/job-runs/{artifact_id}",
    response_model=JobRunRead,
    summary="Read a job run: its progress, counts, report and open suggestions",
)
def read_run(workspace_id: int, artifact_id: int, session: SessionDep) -> JobRunRead:
    """Any version of a run's copy reads the run."""
    found = run_read(session, workspace_id, artifact_id)
    if found is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "NOT_FOUND", "message": "No such job run."},
        )
    return found


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
