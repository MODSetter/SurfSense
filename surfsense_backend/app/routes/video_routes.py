"""
Video generation route.

POST /video/generate-code
  Accepts topic, source_content, and optional error correction context.
  Calls the configured agent LLM with the Remotion system prompt and returns
  the raw TSX component code string.  The frontend (Next.js) is responsible
  for compiling, validating, and retrying with real Babel errors.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.video.prompts import REMOTION_SYSTEM_PROMPT
from app.db import Permission, get_async_session
from app.services.llm_service import get_agent_llm
from app.users import User, current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^(`{3,})(?:tsx|ts|jsx|js|typescript|javascript)?\s*\n")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    m = _FENCE_RE.match(stripped)
    if m:
        fence = m.group(1)
        if stripped.endswith(fence):
            stripped = stripped[m.end() :]
            stripped = stripped[: -len(fence)].rstrip()
    return stripped


class VideoGenerateCodeRequest(BaseModel):
    search_space_id: int
    topic: str = Field(..., max_length=200)
    source_content: str
    error: str | None = None
    attempt: int = Field(default=1, ge=1, le=3)


class VideoGenerateCodeResponse(BaseModel):
    code: str


@router.post("/video/generate-code", response_model=VideoGenerateCodeResponse)
async def generate_video_code(
    data: VideoGenerateCodeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Generate a Remotion TSX component from topic and source content.

    Called by the Next.js API route which handles compilation, validation,
    and client-driven retry with real Babel errors.
    """
    await check_permission(
        session,
        user,
        data.search_space_id,
        Permission.CHAT_CREATE.value,
        "You don't have permission to generate videos in this search space",
    )

    llm = await get_agent_llm(session, data.search_space_id)
    if not llm:
        raise HTTPException(
            status_code=422,
            detail="No LLM configured. Please configure a language model in Settings.",
        )

    base_prompt = (
        f"Create an animated Remotion video component.\n\n"
        f"Title: {data.topic}\n\n"
        f"Content:\n{data.source_content}"
    )

    if data.error and data.attempt > 1:
        user_content = (
            f"{base_prompt}\n\n"
            f"## CORRECTION REQUIRED (ATTEMPT {data.attempt}/3)\n"
            f"Your previous attempt failed to compile with this error:\n"
            f"```\n{data.error}\n```\n\n"
            f"Fix the error and return the complete corrected code."
        )
    else:
        user_content = base_prompt

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=REMOTION_SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]
        )
    except Exception as e:
        logger.exception("[video/generate-code] LLM call failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e!s}") from e

    raw = response.content
    if not raw or not isinstance(raw, str):
        raise HTTPException(status_code=502, detail="LLM returned empty content.")

    code = _strip_code_fences(raw)
    if not code:
        raise HTTPException(
            status_code=502,
            detail="Could not extract component code from LLM response.",
        )

    logger.info(
        "[video/generate-code] Generated component for '%s' attempt=%d (%d chars)",
        data.topic,
        data.attempt,
        len(code),
    )

    return VideoGenerateCodeResponse(code=code)
