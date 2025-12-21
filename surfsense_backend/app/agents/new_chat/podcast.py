"""
Podcast generation tool for the new chat agent.

This module provides a factory function for creating the generate_podcast tool
that submits a Celery task for background podcast generation. The frontend
polls for completion and auto-updates when the podcast is ready.
"""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession


def create_generate_podcast_tool(
    search_space_id: int,
    db_session: AsyncSession,
    user_id: str,
):
    """
    Factory function to create the generate_podcast tool with injected dependencies.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session (not used - Celery creates its own)
        user_id: The user's ID (as string)

    Returns:
        A configured tool function for generating podcasts
    """

    @tool
    async def generate_podcast(
        source_content: str,
        podcast_title: str = "SurfSense Podcast",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a podcast from the provided content.

        Use this tool when the user asks to create, generate, or make a podcast.
        Common triggers include phrases like:
        - "Give me a podcast about this"
        - "Create a podcast from this conversation"
        - "Generate a podcast summary"
        - "Make a podcast about..."
        - "Turn this into a podcast"

        The tool will start generating a podcast in the background.
        The podcast will be available once generation completes.

        Args:
            source_content: The text content to convert into a podcast.
                           This can be a summary, research findings, or any text
                           the user wants transformed into an audio podcast.
            podcast_title: Title for the podcast (default: "SurfSense Podcast")
            user_prompt: Optional instructions for podcast style, tone, or format.
                        For example: "Make it casual and fun" or "Focus on the key insights"

        Returns:
            A dictionary containing:
            - status: "processing" (task submitted) or "error"
            - task_id: The Celery task ID for polling status
            - title: The podcast title
        """
        try:
            # Import Celery task here to avoid circular imports
            from app.tasks.celery_tasks.podcast_tasks import (
                generate_content_podcast_task,
            )

            # Submit Celery task for background processing
            task = generate_content_podcast_task.delay(
                source_content=source_content,
                search_space_id=search_space_id,
                user_id=str(user_id),
                podcast_title=podcast_title,
                user_prompt=user_prompt,
            )

            print(f"[generate_podcast] Submitted Celery task: {task.id}")

            # Return immediately with task_id for polling
            return {
                "status": "processing",
                "task_id": task.id,
                "title": podcast_title,
                "message": "Podcast generation started. This may take a few minutes.",
            }

        except Exception as e:
            error_message = str(e)
            print(f"[generate_podcast] Error submitting task: {error_message}")
            return {
                "status": "error",
                "error": error_message,
                "title": podcast_title,
                "task_id": None,
            }

    return generate_podcast
