"""Chat tool: prepare video generation from conversation content.

When the chat agent decides to create a video, it calls this tool.
The tool returns the topic and source_content. The frontend then:
  1. Calls POST /api/v1/video/generate-script to get VideoInput JSON
  2. Renders the video via Remotion Lambda
  3. Displays the result
"""

import logging
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
        """Prepare video generation from conversation content.

        Use this when the user asks to create, generate, or make a video,
        animate content, export as video, or make an animated summary.

        IMPORTANT — source_content must be structured for VISUAL animation,
        NOT a text essay. Organize the content by themes with short phrases:
        - Key statistics and numbers
        - Hierarchies and taxonomies
        - Processes and sequences
        - Comparisons and contrasts
        - Relationships between concepts
        - Important definitions and quotes

        Keep labels SHORT (max 6-8 words) and descriptions concise (max 2 sentences).

        Args:
            topic: Short title for the video (max ~8 words).
            source_content: Structured content organized by themes for visual animation.

        Returns:
            A dictionary with topic and source_content for the frontend to render.
        """
        logger.info("[generate_video] Preparing video for '%s'", topic)

        return {
            "status": "success",
            "topic": topic,
            "source_content": source_content,
            "search_space_id": search_space_id,
        }

    return generate_video
