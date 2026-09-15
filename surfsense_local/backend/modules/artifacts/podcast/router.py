from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.artifacts.podcast.brief import PodcastBrief
from modules.artifacts.podcast.service import open_brief
from modules.llm.providers.protocols import Voice
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(tags=["studio"])


class BriefRead(BaseModel):
    brief: PodcastBrief
    voices: list[Voice]


@router.get(
    "/workspaces/{workspace_id}/studio/podcast/brief",
    response_model=BriefRead,
    summary="The podcast brief to review before generating",
)
def podcast_brief(workspace: WorkspaceDep, session: SessionDep) -> BriefRead:
    brief, voices = open_brief(session, workspace)
    return BriefRead(brief=brief, voices=voices)
