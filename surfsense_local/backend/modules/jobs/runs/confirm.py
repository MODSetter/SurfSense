"""Confirm a run's suggested answers in one step: the next version of its revised copy writes each
as the job would have written it, so the person who checked them need not type them in."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.service import create_next_version
from modules.artifacts.revised_copies.versions import revision_base
from modules.documents.models import DocumentStatus
from modules.jobs.runs.record import JOB_RUN_KEY, job_run_of
from modules.jobs.runs.start import JobRunRefusedError
from modules.jobs.workbook_rows.operations import confirm_operations


def confirm_suggestions(
    session: Session,
    workspace_id: int,
    artifact_id: int,
    cells: list[tuple[str, str]] | None = None,
) -> Artifact:
    """The version that confirms the suggestions at `cells` (sheet, answer cell), or every one
    not yet confirmed. The run keeps which version confirmed which, so none is confirmed twice
    while that version stands; the caller commits that record."""
    artifact = session.get(Artifact, artifact_id)
    run = job_run_of(artifact.artifact_metadata) if artifact is not None else None
    if artifact is None or artifact.workspace_id != workspace_id or run is None:
        raise JobRunRefusedError(
            f"There is no job run {artifact_id} in this workspace."
        )
    report = run.get("report")
    if report is None:
        raise JobRunRefusedError("The run is still answering: confirm once it is done.")
    done = _confirmed(session, run)
    open_ = {
        (a["sheet"], a["cell"]): a
        for a in report["answers"]
        if a.get("confirm") and (a["sheet"], a["cell"]) not in done
    }
    if cells is None:
        chosen = list(open_.values())
    else:
        missing = [cell for cell in dict.fromkeys(cells) if cell not in open_]
        if missing:
            named = ", ".join(f"{sheet}!{cell}" for sheet, cell in missing)
            raise JobRunRefusedError(f"No suggestion is left to confirm at {named}.")
        chosen = [open_[cell] for cell in dict.fromkeys(cells)]
    if not chosen:
        raise JobRunRefusedError("The run has no suggested answers left to confirm.")
    try:
        base = revision_base(session, workspace_id, artifact_id)
        made = create_next_version(
            session,
            workspace_id,
            base,
            action="edit",
            operations=confirm_operations(chosen, report["sheets"]),
            chat_thread_id=base.artifact.chat_thread_id,
        )
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused
    # Making the version committed it. Were the record below lost, its suggestions would only
    # be offered again, and confirming one twice writes the same cells twice.
    _record(artifact, run, chosen, made.id)
    return made


def _confirmed(session: Session, run: dict[str, Any]) -> set[tuple[str, str]]:
    """The cells a version confirms that is made or still being made. A version that failed,
    was cancelled or was deleted confirmed nothing, so its suggestions are offered again."""
    held = set()
    for confirmed in run.get("confirmed") or []:
        version = session.get(Artifact, confirmed.get("artifact_id") or 0)
        if version is None or version.document.status in (
            DocumentStatus.FAILED,
            DocumentStatus.CANCELLED,
        ):
            continue
        held.add((confirmed["sheet"], confirmed["cell"]))
    return held


def _record(
    artifact: Artifact, run: dict[str, Any], chosen: list[dict], version: int
) -> None:
    """Which suggestions which version confirms."""
    meta = dict(artifact.artifact_metadata or {})
    meta[JOB_RUN_KEY] = {
        **run,
        "confirmed": [
            *(run.get("confirmed") or []),
            *(
                {"sheet": a["sheet"], "cell": a["cell"], "artifact_id": version}
                for a in chosen
            ),
        ],
    }
    artifact.artifact_metadata = meta
