from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.podcast import brief
from modules.llm.resolution import ModelResolutionError
from modules.llm.voices.roster import SpeechRoster, speech_voices
from modules.workspaces.models import Workspace

FORMAT = "podcast"


def open_brief(
    session: Session, workspace: Workspace
) -> tuple[brief.PodcastBrief, SpeechRoster]:
    """The brief the form opens with, and the voices it may pick from.

    The last episode's brief comes back when it still fits the catalog, so a
    returning user changes only what differs; otherwise the defaults.
    """
    try:
        roster = speech_voices(session)
    except ModelResolutionError as error:
        # The reason with its code, as create and regenerate send it, so the
        # interface shows its own sentence.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Needs an audio model", "code": "needs_audio"},
        ) from error

    last = session.scalars(
        select(Artifact)
        .where(Artifact.workspace_id == workspace.id, Artifact.format == FORMAT)
        .order_by(Artifact.id.desc())
        .limit(1)
    ).first()
    options = (last.artifact_metadata or {}).get("options") if last else None
    if options is not None:
        try:
            return brief.validated(roster.voices, options), roster
        except ValueError:
            pass
    return brief.proposed(roster.voices), roster
