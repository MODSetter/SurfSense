"""Chat tool: generate a video from conversation content.

When the chat agent decides to create a video, it calls this tool.
The tool invokes the backend video pipeline (LLM -> sandbox -> tsc ->
render -> MP4) and returns the video URL for the frontend to display.
"""

import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def create_generate_video_tool(
    search_space_id: int,
    thread_id: int,
    db_session: AsyncSession,
):
    @tool
    async def generate_video(
        topic: str,
        source_content: str,
    ) -> dict[str, Any]:
        """Generate an animated Remotion video from conversation content.

        Use this when the user asks to create, generate, or make a video,
        animate content, export as video, or make an animated summary.

        IMPORTANT — source_content must be structured for VISUAL animation,
        NOT a text essay. Provide 4-8 scenes as short bullet points with:
        - A scene label (e.g. "Scene 1: Core Philosophy")
        - 2-4 key concepts per scene as SHORT phrases (max 6 words each)
        - Visual hints where helpful (e.g. "show layered diagram", "animate flow arrows")

        Do NOT write full paragraphs or long explanations. The video renderer
        turns each concept into animated graphics — long text will be unreadable.

        Good example:
          Scene 1: What is DDD?
          - Software mirrors business domain
          - Deep collaboration with experts
          Scene 2: Ubiquitous Language
          - Shared vocabulary: devs + business
          - Same terms in code and conversation
          Scene 3: Layered Architecture (show stacked diagram)
          - Presentation → Application → Domain → Infrastructure
          - Domain layer stays independent

        Bad example:
          "Domain-Driven Design is a software development approach focused on
           modeling complex business domains and aligning software design with
           real-world business concepts. The main idea is that..."

        Args:
            topic: Short title for the video (max ~8 words).
            source_content: Scene-structured bullet points for visual animation (NOT prose).

        Returns:
            A dictionary with the video URL or an error message.
        """
        logger.info("[generate_video] Starting pipeline for '%s'", topic)

        try:
            from app.agents.video import generate_video as run_video_pipeline

            rendered_video_path = await run_video_pipeline(
                session=db_session,
                search_space_id=search_space_id,
                thread_id=thread_id,
                topic=topic,
                source_content=source_content,
            )

            video_filename = Path(rendered_video_path).name
            video_url = f"/api/v1/video/files/{thread_id}/{video_filename}"

            logger.info("[generate_video] Video ready at: %s", video_url)
            return {
                "status": "success",
                "mp4_url": video_url,
                "topic": topic,
            }

        except Exception as exc:
            logger.exception("[generate_video] Pipeline failed for '%s'", topic)
            return {
                "status": "error",
                "error": str(exc),
                "topic": topic,
            }

    return generate_video
