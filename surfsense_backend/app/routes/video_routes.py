import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.video.prompts import MAX_ATTEMPTS
from app.db import Permission, get_async_session
from app.services.video_service import generate_video_code
from app.users import User, current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


class VideoGenerateCodeRequest(BaseModel):
    search_space_id: int
    topic: str = Field(..., max_length=200)
    source_content: str
    error: str | None = None
    attempt: int = Field(default=1, ge=1, le=MAX_ATTEMPTS)


class VideoGenerateCodeResponse(BaseModel):
    code: str


@router.post("/video/generate-code", response_model=VideoGenerateCodeResponse)
async def generate_video_code_route(
    data: VideoGenerateCodeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_permission(
        session,
        user,
        data.search_space_id,
        Permission.CHATS_CREATE.value,
        "You don't have permission to generate videos in this search space",
    )

    try:
        code = await generate_video_code(
            session=session,
            search_space_id=data.search_space_id,
            topic=data.topic,
            source_content=data.source_content,
            attempt=data.attempt,
            error=data.error,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("[video/generate-code] Service call failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e!s}") from e

    return VideoGenerateCodeResponse(code=code)
