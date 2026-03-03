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

        Args:
            topic: Short title for the video (max ~8 words).
            source_content: Comprehensive summary of the content to animate.

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
