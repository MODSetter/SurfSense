"""A workspace's job runs as the Jobs screen reads them: how far each has got, its counts, the
suggested answers still open, and its copy's newest versions.

A run is v1 of its revised copy; any later version of that copy names the run too.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.versions import IN_FLIGHT, versions_of_roots
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus
from modules.jobs.runs.open_suggestions import open_suggestions, taken_cells
from modules.jobs.runs.record import PROGRESS_KEY, job_run_of
from modules.jobs.runs.run_tally import run_tally


class RunProgressRead(BaseModel):
    done: int
    total: int


class RunTallyRead(BaseModel):
    questions: int
    answered: int
    for_person: int
    suggested: int
    skipped: int


class JobRunSummary(BaseModel):
    artifact_id: int  # the run, v1 of its copy
    title: str
    job: str
    pack_id: str
    pack_version: str
    status: DocumentStatus
    error: str | None
    created_at: datetime
    # Null until the worker has found the questions, and until it has a report.
    progress: RunProgressRead | None
    tally: RunTallyRead | None
    open_suggestion_count: int
    newest_version_id: int
    newest_version_number: int
    newest_ready_version_id: int | None
    # Whether any version of the copy is pending or processing.
    running: bool


class OpenSuggestion(BaseModel):
    sheet: str
    cell: str
    question: str
    suggested: str
    written: str  # as the cell's own dropdown spells it
    comment: str | None


class ConfirmedCell(BaseModel):
    sheet: str
    cell: str
    artifact_id: int  # the version that confirmed it


class JobRunRead(JobRunSummary):
    pack: str
    report: dict[str, Any] | None
    open_suggestions: list[OpenSuggestion]
    confirmed: list[ConfirmedCell]


def run_summaries(
    session: Session, workspace_id: int, limit: int
) -> list[JobRunSummary]:
    """The workspace's runs, newest first: one query for them and one for their versions."""
    runs = list(
        session.scalars(
            select(Artifact)
            .join(Artifact.document)
            .options(contains_eager(Artifact.document))
            .where(
                Artifact.workspace_id == workspace_id,
                func.json_type(Artifact.artifact_metadata, "$.job_run") == "object",
            )
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
            .limit(limit)
        )
    )
    versions = versions_of_roots(session, workspace_id, [run.id for run in runs])
    return [JobRunSummary(**_summary(run, versions[run.id] or [run])) for run in runs]


def run_read(
    session: Session, workspace_id: int, artifact_id: int
) -> JobRunRead | None:
    """The run `artifact_id` is or is a later version of; None when it is no run of this
    workspace's."""
    run = _run_named(session, workspace_id, artifact_id)
    if run is None:
        return None
    versions = versions_of_roots(session, workspace_id, [run.id])[run.id] or [run]
    record = job_run_of(run.artifact_metadata) or {}
    report = record.get("report")
    still_open = (
        open_suggestions(report, taken_cells(versions, run.id)) if report else []
    )
    return JobRunRead(
        **_summary(run, versions),
        pack=f"{record['pack_id']} {record['pack_version']}",
        report=report,
        open_suggestions=[
            OpenSuggestion(
                sheet=answer["sheet"],
                cell=answer["cell"],
                question=answer["question"],
                suggested=answer["confirm"]["answer"],
                written=answer["confirm"]["written"],
                comment=answer["confirm"].get("comment"),
            )
            for answer in still_open
        ],
        confirmed=[ConfirmedCell(**cell) for cell in record.get("confirmed") or []],
    )


def _run_named(
    session: Session, workspace_id: int, artifact_id: int
) -> Artifact | None:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        return None
    if job_run_of(artifact.artifact_metadata) is not None:
        return artifact
    version = version_of(artifact.artifact_metadata)
    if version is None or version.root == artifact.id:
        return None
    root = session.get(Artifact, version.root)
    if (
        root is None
        or root.workspace_id != workspace_id
        or job_run_of(root.artifact_metadata) is None
    ):
        return None
    return root


def _summary(run: Artifact, versions: list[Artifact]) -> dict[str, Any]:
    """The summary's fields; `versions` are the run's copy's, newest first."""
    record = job_run_of(run.artifact_metadata) or {}
    report = record.get("report")
    newest = versions[0]
    ready = next(
        (v for v in versions if v.document.status is DocumentStatus.READY), None
    )
    newest_version = version_of(newest.artifact_metadata)
    return {
        "artifact_id": run.id,
        "title": run.document.title,
        "job": record["job"],
        "pack_id": record["pack_id"],
        "pack_version": record["pack_version"],
        "status": run.document.status,
        "error": run.document.error_message,
        "created_at": run.created_at,
        "progress": record.get(PROGRESS_KEY),
        "tally": run_tally(report),
        "open_suggestion_count": (
            len(open_suggestions(report, taken_cells(versions, run.id)))
            if report
            else 0
        ),
        "newest_version_id": newest.id,
        "newest_version_number": newest_version.number if newest_version else 1,
        "newest_ready_version_id": ready.id if ready is not None else None,
        "running": any(v.document.status in IN_FLIGHT for v in versions),
    }
