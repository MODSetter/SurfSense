import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.agents.new_chat.tools.video.prompts import MAX_ATTEMPTS
from app.db import NewChatMessage, Permission, get_async_session
from app.routes.new_chat_routes import check_thread_access
from app.services.video_service import generate_video_code
from app.users import User, current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)

_VIDEO_FILES_DIR = Path(os.environ.get("SANDBOX_FILES_DIR", "sandbox_files")) / "video"


class VideoGenerateCodeRequest(BaseModel):
    search_space_id: int
    topic: str = Field(..., max_length=200)
    source_content: str
    error: str | None = None
    attempt: int = Field(default=1, ge=1, le=MAX_ATTEMPTS)


class VideoGenerateCodeResponse(BaseModel):
    code: str


class VideoUpdateCodeRequest(BaseModel):
    message_id: int
    tool_call_id: str
    code: str


class VideoGenerateAgentRequest(BaseModel):
    search_space_id: int
    thread_id: int | str
    topic: str = Field(..., max_length=400)
    source_content: str


class VideoGenerateAgentResponse(BaseModel):
    mp4_url: str


@router.post("/video/generate-code", response_model=VideoGenerateCodeResponse)
async def generate_video_code_route(
    data: VideoGenerateCodeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to generate videos in this search space",
        )

        code = await generate_video_code(
            session=session,
            search_space_id=data.search_space_id,
            topic=data.topic,
            source_content=data.source_content,
            attempt=data.attempt,
            error=data.error,
        )
        return VideoGenerateCodeResponse(code=code)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("[video/generate-code] Service call failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e!s}") from e


@router.patch("/video/update-code")
async def update_video_code_route(
    data: VideoUpdateCodeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(NewChatMessage)
            .where(NewChatMessage.id == data.message_id)
            .options(selectinload(NewChatMessage.thread))
        )
        message = result.scalar_one_or_none()
        if not message:
            logger.warning("[video/update-code] Message %d not found, skipping", data.message_id)
            return {"ok": False}

        await check_thread_access(session, message.thread, user)

        content = message.content
        if not isinstance(content, list):
            logger.warning(
                "[video/update-code] Unexpected content format for message=%d, skipping",
                data.message_id,
            )
            return {"ok": False}

        updated = False
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "tool-call"
                and part.get("toolCallId") == data.tool_call_id
            ):
                if not isinstance(part.get("result"), dict):
                    part["result"] = {}
                part["result"]["code"] = data.code
                updated = True
                break

        if not updated:
            logger.warning(
                "[video/update-code] tool_call_id=%s not found in message=%d, skipping",
                data.tool_call_id,
                data.message_id,
            )
            return {"ok": False}

        flag_modified(message, "content")
        await session.commit()

        logger.info(
            "[video/update-code] Persisted validated code for message=%d tool_call=%s (%d chars)",
            data.message_id,
            data.tool_call_id,
            len(data.code),
        )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        logger.warning(
            "[video/update-code] Failed to persist code for message=%d, skipping",
            data.message_id,
            exc_info=True,
        )
        return {"ok": False}


@router.post("/video/generate-agent", response_model=VideoGenerateAgentResponse)
async def generate_video_agent_route(
    data: VideoGenerateAgentRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Generate a video using the Remotion deepagent pipeline.

    Runs the full agent loop in a Daytona sandbox:
      write → tsc validate → render → return MP4 URL.
    """
    try:
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to generate videos in this search space",
        )

        from app.services.video_agent_service import generate_video_with_agent

        local_path = await generate_video_with_agent(
            session=session,
            search_space_id=data.search_space_id,
            thread_id=data.thread_id,
            topic=data.topic,
            source_content=data.source_content,
        )

        # Build a URL the frontend can use to stream the MP4
        filename = Path(local_path).name
        mp4_url = f"/api/v1/video/files/{data.thread_id}/{filename}"
        return VideoGenerateAgentResponse(mp4_url=mp4_url)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("[video/generate-agent] Agent pipeline failed")
        raise HTTPException(status_code=502, detail=f"Video generation failed: {e!s}") from e


@router.get("/video/files/{thread_id}/{filename}")
async def serve_video_file(
    thread_id: str,
    filename: str,
    user: User = Depends(current_active_user),
):
    """Serve a locally cached MP4 file produced by the video deepagent."""
    # Basic path-traversal guard
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = _VIDEO_FILES_DIR / thread_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
    )
