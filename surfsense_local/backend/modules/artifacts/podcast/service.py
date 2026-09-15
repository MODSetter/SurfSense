from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.podcast import brief
from modules.llm.providers.protocols import Voice
from modules.llm.resolution import ModelResolutionError, resolve_text_to_speech
from modules.workspaces.models import Workspace

FORMAT = "podcast"


def open_brief(
    session: Session, workspace: Workspace
) -> tuple[brief.PodcastBrief, list[Voice]]:
    """The brief the form opens with, and the voices it may pick from.

    The last episode's brief comes back when it still fits the catalog, so a
    returning user changes only what differs; otherwise the defaults.
    """
    try:
        voices = resolve_text_to_speech().voices()
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Voice model required") from error

    last = session.scalars(
        select(Artifact)
        .where(Artifact.workspace_id == workspace.id, Artifact.format == FORMAT)
        .order_by(Artifact.id.desc())
        .limit(1)
    ).first()
    options = (last.artifact_metadata or {}).get("options") if last else None
    if options is not None:
        try:
            return brief.validated(voices, options), voices
        except ValueError:
            pass
    return brief.proposed(voices), voices
