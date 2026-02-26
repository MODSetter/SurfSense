import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from app.db import async_session_maker
from app.services.llm_service import get_agent_llm

from .prompts import REMOTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    m = re.match(r"^(`{3,})(?:tsx|ts|jsx|js|typescript|javascript)?\s*\n", stripped)
    if m:
        fence = m.group(1)
        if stripped.endswith(fence):
            stripped = stripped[m.end() :]
            stripped = stripped[: -len(fence)].rstrip()
    return stripped


def create_generate_video_tool(search_space_id: int):
    @tool
    async def generate_video(
        topic: str,
        source_content: str,
    ) -> dict[str, Any]:
        """Generate an animated Remotion video component from conversation content.

        Use this when the user asks to create, generate, or make a video,
        animate content, export as video or make an animated summary.

        Args:
            topic: Short title for the video (max ~8 words).
            source_content: Comprehensive summary of the content to animate.

        Returns:
            Dict with status, code (TSX component string), title, and duration_frames.
        """
        try:
            async with async_session_maker() as session:
                llm = await get_agent_llm(session, search_space_id)

            if not llm:
                return {
                    "status": "failed",
                    "error": "No LLM configured. Please configure a language model in Settings.",
                    "title": topic,
                }

            response = await llm.ainvoke(
                [
                    SystemMessage(content=REMOTION_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            f"Create an animated Remotion video component.\n\n"
                            f"Title: {topic}\n\n"
                            f"Content:\n{source_content}"
                        )
                    ),
                ]
            )

            raw = response.content
            if not raw or not isinstance(raw, str):
                return {
                    "status": "failed",
                    "error": "LLM returned empty content.",
                    "title": topic,
                }

            code = _strip_code_fences(raw)
            if not code:
                return {
                    "status": "failed",
                    "error": "Could not extract component code from LLM response.",
                    "title": topic,
                }

            logger.info(
                "[generate_video] Generated component for '%s' (%d chars)",
                topic,
                len(code),
            )

            return {
                "status": "ready",
                "code": code,
                "title": topic,
                "duration_frames": 180,
            }

        except Exception as e:
            logger.exception("[generate_video] Error: %s", e)
            return {
                "status": "failed",
                "error": str(e),
                "title": topic,
            }

    return generate_video
