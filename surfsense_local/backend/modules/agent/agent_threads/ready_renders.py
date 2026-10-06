"""A render step's link to the version it made, and whether that version made the document new.

A render still being made when its call answered links its version once Studio
made it. `created` is true for a document's first ready version: v1, or the
first to succeed after failed tries, which the user never had. An earlier
version Studio is running again, or whose re-run failed, keeps the file its
ready run wrote, so the user still had it.
"""

from dataclasses import asdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.agent.agent_threads.steps import RENDER_STEP
from modules.agent.tool_endpoint.rendered_label import queued_artifact
from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import Document, DocumentStatus
from shared.db import is_locked


def link_ready_renders(
    session: Session, workspace_id: int, turns: list[dict[str, Any]]
) -> None:
    """Link every render step of these turns, as `link_render` does one."""
    for turn in turns:
        for step in (turn.get("content") or {}).get("steps") or []:
            link_render(session, workspace_id, step)


def link_render(session: Session, workspace_id: int, step: dict[str, Any]) -> None:
    """Fill a render step's `artifact` once its version is ready, with `created` beside it.

    A step whose version is gone keeps what its result named, without `created`.
    """
    if step.get("tool") != RENDER_STEP:
        return
    named = step.get("artifact")
    if named is None:
        queued = queued_artifact(step.get("output") or "")
        named = asdict(queued) if queued is not None else None
    if named is None:
        return
    artifact = session.get(Artifact, named["id"])
    if (
        artifact is None
        or artifact.workspace_id != workspace_id
        or artifact.document.status is not DocumentStatus.READY
    ):
        return
    step["artifact"] = {**named, "created": _first_ready(session, artifact)}


def link_live_render(session: Session, workspace_id: int, step: dict[str, Any]) -> None:
    """As `link_render`, but a write lock held past the busy wait leaves the step as it was.

    Studio can hold the lock that long; the turn must not stop for a label that
    reading the thread back fills in.
    """
    try:
        link_render(session, workspace_id, step)
    except OperationalError as error:
        session.rollback()
        if not is_locked(error):
            raise


def _first_ready(session: Session, artifact: Artifact) -> bool:
    """Whether no earlier version of its document is ready, or was before a re-run."""
    version = version_of(artifact.artifact_metadata)
    if version is None:
        return True
    number = Artifact.artifact_metadata["version"]["number"].as_integer()
    earlier = session.scalar(
        select(Artifact.id)
        .join(Document, Artifact.document_id == Document.id)
        .where(
            Artifact.workspace_id == artifact.workspace_id,
            Artifact.artifact_metadata["version"]["root"].as_integer() == version.root,
            number < version.number,
            or_(
                Document.status == DocumentStatus.READY,
                Artifact.files.any(ArtifactFile.role == ArtifactFileRole.PRIMARY),
            ),
        )
        .limit(1)
    )
    return earlier is None
