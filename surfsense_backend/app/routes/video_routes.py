"""Video routes: script generation."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.video.script_generator import generate_video_script
from app.db import get_async_session
from app.schemas.video import GenerateScriptRequest, VideoInput

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/video/generate-script", response_model=VideoInput)
async def generate_script(
    request: GenerateScriptRequest,
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Generate a VideoInput JSON from topic + source content.

    The LLM produces structured output matching the VideoInput schema.
    The frontend then renders this JSON via Remotion Lambda.
    """
    try:
        result = await generate_video_script(
            session=session,
            search_space_id=search_space_id,
            topic=request.topic,
            source_content=request.source_content,
        )
        return result
    except Exception as exc:
        logger.exception("[video/generate-script] Failed for topic '%s'", request.topic)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
