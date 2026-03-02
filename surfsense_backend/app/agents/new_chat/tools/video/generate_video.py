import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_generate_video_tool(search_space_id: int, thread_id: int):
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
            Dict signalling the frontend to start video generation.
        """
        logger.info(
            "[generate_video] Signalling frontend to generate video for '%s'", topic
        )
        return {
            "status": "prompt_ready",
            "search_space_id": search_space_id,
            "thread_id": thread_id,
            "topic": topic,
            "source_content": source_content,
        }

    return generate_video
