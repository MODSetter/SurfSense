"""A run's suggested answers still open: those whose answer cell no later version of the run's copy
that stands writes.

Read from the versions themselves, never from a record of their ids, which the database hands
out again once a row is deleted. A version that failed or was cancelled wrote nothing, and a
deleted one is gone, so their suggestions are open again; a cell a person answered in a
version of their own is taken.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.revised_copies.versions import versions_of
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus

_WROTE_NOTHING = (DocumentStatus.FAILED, DocumentStatus.CANCELLED)


def taken_cells(versions: Iterable[Artifact], run_id: int) -> set[tuple[str, str]]:
    """The cells the versions after the run write, made or still being made."""
    taken: set[tuple[str, str]] = set()
    for later in versions:
        if later.id == run_id or later.document.status in _WROTE_NOTHING:
            continue
        for op in (revision_of(later.artifact_metadata) or {}).get("operations") or []:
            if op.get("op") == "set_cell":
                taken.add((op.get("sheet"), op.get("cell")))
    return taken


def cells_taken(
    session: Session, workspace_id: int, artifact: Artifact
) -> set[tuple[str, str]]:
    """`taken_cells` for the run `artifact`, its copy's versions read here."""
    version = version_of(artifact.artifact_metadata)
    if version is None:
        return set()
    return taken_cells(versions_of(session, workspace_id, version.root), artifact.id)


def open_suggestions(
    report: dict[str, Any], taken: set[tuple[str, str]]
) -> list[dict[str, Any]]:
    """The report's answers one step can confirm whose cell is not taken, in report order."""
    return [
        answer
        for answer in report["answers"]
        if answer.get("confirm") and (answer["sheet"], answer["cell"]) not in taken
    ]
