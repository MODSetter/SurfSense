"""Confirm a run's suggested answers in one step: the next version of its revised copy writes each
as the job would have written it, so the person who checked them need not type them in."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.service import create_next_version
from modules.artifacts.revised_copies.versions import revision_base
from modules.jobs.runs.open_suggestions import cells_taken, open_suggestions
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
    still open: a suggestion is open while no later version of the run's copy that stands writes
    its answer cell. The run also keeps which version confirmed which, for the record; the
    caller commits it."""
    artifact = session.get(Artifact, artifact_id)
    run = job_run_of(artifact.artifact_metadata) if artifact is not None else None
    if artifact is None or artifact.workspace_id != workspace_id or run is None:
        raise JobRunRefusedError(
            f"There is no job run {artifact_id} in this workspace."
        )
    report = run.get("report")
    if report is None:
        raise JobRunRefusedError("The run is still answering: confirm once it is done.")
    taken = cells_taken(session, workspace_id, artifact)
    open_ = {(a["sheet"], a["cell"]): a for a in open_suggestions(report, taken)}
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
    # Making the version committed it; the record below is history only, so were it lost,
    # nothing would be offered twice.
    _record(artifact, run, chosen, made.id)
    return made


def _record(
    artifact: Artifact, run: dict[str, Any], chosen: list[dict], version: int
) -> None:
    """Which suggestions which version confirmed: history, which nothing offered is read from."""
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
