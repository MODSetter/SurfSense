from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.artifacts.podcast.brief import PodcastBrief, languages
from modules.artifacts.podcast.service import open_brief
from modules.llm.providers.protocols import Voice
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(tags=["studio"])


class VoicedByRead(BaseModel):
    server: str
    model: str


class BriefRead(BaseModel):
    brief: PodcastBrief
    # Empty only for a server model with no voices added yet.
    voices: list[Voice]
    voices_source: Literal["local", "server", "saved"]
    # The server that voices it; None for a model on this computer.
    voiced_by: VoicedByRead | None
    languages: list[str]


@router.get(
    "/workspaces/{workspace_id}/studio/podcast/brief",
    response_model=BriefRead,
    summary="The podcast brief to review before generating",
)
def podcast_brief(workspace: WorkspaceDep, session: SessionDep) -> BriefRead:
    brief, roster = open_brief(session, workspace)
    by = roster.voiced_by
    return BriefRead(
        brief=brief,
        voices=roster.voices,
        voices_source=roster.source,
        voiced_by=VoicedByRead(server=by.server, model=by.model) if by else None,
        languages=languages(roster.voices),
    )
