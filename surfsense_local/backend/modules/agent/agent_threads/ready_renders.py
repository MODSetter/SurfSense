"""A render still being made when its call answered links its version once Studio made it."""

from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.agent_threads.steps import RENDER_STEP
from modules.agent.tool_endpoint.rendered_label import queued_artifact
from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus


def link_ready_renders(
    session: Session, workspace_id: int, turns: list[dict[str, Any]]
) -> None:
    """Fill each such step's `artifact`, read back as a render that was ready in time is."""
    for turn in turns:
        for step in (turn.get("content") or {}).get("steps") or []:
            if step.get("tool") != RENDER_STEP or step.get("artifact") is not None:
                continue
            queued = queued_artifact(step.get("output") or "")
            if queued is not None and _ready(session, workspace_id, queued.id):
                step["artifact"] = asdict(queued)


def _ready(session: Session, workspace_id: int, artifact_id: int) -> bool:
    artifact = session.get(Artifact, artifact_id)
    return (
        artifact is not None
        and artifact.workspace_id == workspace_id
        and artifact.document.status is DocumentStatus.READY
    )
