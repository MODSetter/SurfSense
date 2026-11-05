"""The job tool: run an installed job pack's job on the selected workbook and sources.

Offered only while a pack is installed, and listed with that pack's jobs. The run is a
Studio job, as a revised copy is; the tool waits for it as long as a call may last.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.render_document import CALL_SECONDS, WAIT_SECONDS
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus
from modules.jobs.packs.installed import installed_packs
from modules.jobs.runs.record import job_run_of
from modules.jobs.runs.start import JobRunRefusedError, start_job_run

TOOL_NAME = "run_job"
# Exceptions named in the reply; the rest are on the workbook's exceptions sheet.
NAMED_EXCEPTIONS = 12


def job_listing() -> dict[str, Any] | None:
    """The tool as the model is shown it, naming the jobs installed now; None when there are none."""
    jobs = [
        (job.key, job.description)
        for pack in installed_packs()
        for job in pack.manifest.jobs
    ]
    if not jobs:
        return None
    named = "; ".join(f"{key}: {description}" for key, description in jobs)
    return {
        "name": TOOL_NAME,
        "description": (
            "Run an installed SurfSense job on the selected sources. Load the job's "
            f"skill first. Jobs: {named}. The job makes a revised copy in Studio; the "
            "user's file is never changed. Returns the copy's artifact id, the answer "
            "counts and the exceptions a person must look at, or that it is still running."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job": {"type": "string", "enum": [key for key, _ in jobs]},
                "document_id": {
                    "type": "integer",
                    "description": "The workbook to fill in, by the number at the end of its file name.",
                },
                "source_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "The documents to answer from; leave out to use every other selected source.",
                },
            },
            "required": ["job", "document_id"],
        },
    }


def run(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    deadline = time.monotonic() + CALL_SECONDS
    job, document_id = arguments.get("job"), arguments.get("document_id")
    if (
        not isinstance(job, str)
        or not isinstance(document_id, int)
        or isinstance(document_id, bool)
    ):
        raise ToolCallError(
            "Give job, by its name, and document_id, the workbook's number."
        )
    source_ids = arguments.get("source_ids")
    if source_ids is None:
        source_ids = sorted(scope.selected() - {document_id})
    if not isinstance(source_ids, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) for i in source_ids
    ):
        raise ToolCallError("source_ids is a list of source numbers, or left out.")
    scope.refuse_unselected([document_id, *source_ids])
    try:
        artifact = start_job_run(
            session,
            scope.workspace_id,
            job=job,
            workbook_document_id=document_id,
            source_document_ids=source_ids,
            chat_thread_id=scope.thread_id if scope.known else None,
        )
    except JobRunRefusedError as refused:
        session.rollback()
        raise ToolCallError(str(refused)) from refused
    artifact_id = artifact.id
    outcome = wait_for_outcome(
        session, artifact_id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    named = f"The {job} run (artifact {artifact_id})"
    if outcome is None:
        raise ToolCallError(f"{named} was deleted before it finished.")
    if outcome.status is DocumentStatus.FAILED:
        raise ToolCallError(
            f"{named} failed: {outcome.error_message or 'no reason given'}"
        )
    if outcome.status is DocumentStatus.CANCELLED:
        return f"{named} was cancelled in Studio. Ask the user before running it again."
    if outcome.status is not DocumentStatus.READY:
        return (
            f"{named} is still answering. It appears in Studio when it is done: tell the "
            "user so, and do not start it again."
        )
    session.expire_all()
    report = (
        job_run_of(session.get(Artifact, artifact_id).artifact_metadata) or {}
    ).get("report") or {}
    return summary(artifact_id, report)


def summary(artifact_id: int, report: dict[str, Any]) -> str:
    counts = report.get("counts") or {}
    answered = ", ".join(
        f"{counts[k]} {k}" for k in counts if k not in ("blank", "skipped")
    )
    lines = [
        f"Done: version 1 of a revised copy (artifact {artifact_id}) in Studio, with "
        f"{report.get('questions', 0)} questions answered: {answered or 'none'}. "
        f"{counts.get('blank', 0)} answer cells were left blank and "
        f"{counts.get('skipped', 0)} questions were skipped. Each answer's source and "
        'quote is on its "SurfSense answers" sheet; the exceptions are on "SurfSense exceptions".'
    ]
    suggested = report.get("suggested") or 0
    if suggested:
        lines.append(
            f"{suggested} of the questions left to a person carry a suggested answer with "
            "its evidence, such as N/A for a control a provider runs for the firm. Tell the "
            "user; once they have checked them, they may ask you to confirm them with "
            f"confirm_job_suggestions and artifact_id {artifact_id}."
        )
    exceptions = report.get("exceptions") or []
    for sheet, cell, question, _answer, why in exceptions[:NAMED_EXCEPTIONS]:
        lines.append(f"- {sheet}!{cell} ({question[:90]}): {why}")
    if len(exceptions) > NAMED_EXCEPTIONS:
        lines.append(
            f"- and {len(exceptions) - NAMED_EXCEPTIONS} more on the exceptions sheet."
        )
    return "\n".join(lines)


RUN_JOB = Tool(
    listing={"name": TOOL_NAME, "description": "", "inputSchema": {"type": "object"}},
    run=run,
    waits=True,
)
