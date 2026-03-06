"""Video script generator.

Flow: topic + source_content -> LLM (structured output) -> VideoInput JSON.
The frontend then renders the JSON via Remotion Lambda.
"""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.video.script_prompt import SCRIPT_SYSTEM_PROMPT
from app.schemas.video import VideoInput
from app.services.llm_service import get_video_llm

logger = logging.getLogger(__name__)


async def generate_video_script(
    session: AsyncSession,
    search_space_id: int,
    topic: str,
    source_content: str,
) -> VideoInput:
    """Generate a VideoInput script from topic + source content using structured output."""
    llm = await get_video_llm(session, search_space_id)
    if not llm:
        raise ValueError("No LLM configured. Please configure a language model in Settings.")

    structured_llm = llm.with_structured_output(VideoInput)

    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Source Content:\n{source_content}"
    )

    logger.info("[video/script_generator] Generating video script for: '%s'", topic)

    result = await structured_llm.ainvoke([
        SystemMessage(content=SCRIPT_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    logger.info(
        "[video/script_generator] Generated %d scenes for '%s'",
        len(result.scenes),
        topic,
    )
    return result
