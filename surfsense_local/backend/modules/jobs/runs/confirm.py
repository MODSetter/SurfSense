"""Confirm a run's suggested answers in one step: the next version of its revised copy writes each
as the job would have written it, so the person who checked them need not type them in."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.service import create_next_version
from modules.artifacts.revised_copies.versions import revision_base
from modules.artifacts.script_documents.version import next_version_number
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
    not yet confirmed. The run keeps which it confirmed, so none is confirmed twice."""
    artifact = session.get(Artifact, artifact_id)
    run = job_run_of(artifact.artifact_metadata) if artifact is not None else None
    if artifact is None or artifact.workspace_id != workspace_id or run is None:
        raise JobRunRefusedError(
            f"There is no job run {artifact_id} in this workspace."
        )
    report = run.get("report")
    if report is None:
        raise JobRunRefusedError("The run is still answering: confirm once it is done.")
    done = {(c["sheet"], c["cell"]) for c in run.get("confirmed") or []}
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
        # Kept before the version is made: making it commits, and both must land together.
        number = next_version_number(session, workspace_id, base.version.root)
        _record(artifact, run, chosen, number)
        return create_next_version(
            session,
            workspace_id,
            base,
            action="edit",
            operations=confirm_operations(chosen, report["sheets"]),
            chat_thread_id=base.artifact.chat_thread_id,
        )
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused


def _record(
    artifact: Artifact, run: dict[str, Any], chosen: list[dict], after: int
) -> None:
    """Which suggestions were confirmed, and the version number from which they stand."""
    meta = dict(artifact.artifact_metadata or {})
    meta[JOB_RUN_KEY] = {
        **run,
        "confirmed": [
            *(run.get("confirmed") or []),
            *({"sheet": a["sheet"], "cell": a["cell"], "after": after} for a in chosen),
        ],
    }
    artifact.artifact_metadata = meta
