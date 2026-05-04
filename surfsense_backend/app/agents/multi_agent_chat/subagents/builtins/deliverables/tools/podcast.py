"""Factory for a podcast-generation tool that queues background work and returns an ID for polling."""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Podcast, PodcastStatus, shielded_async_session


def create_generate_podcast_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """Create ``generate_podcast`` with bound search space and thread; DB writes use a tool-local session."""
    del db_session  # writes use a fresh tool-local session, see below

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

        Args:
            source_content: The text content to convert into a podcast.
            podcast_title: Title for the podcast (default: "SurfSense Podcast")
            user_prompt: Optional instructions for podcast style, tone, or format.

        Returns:
            A dictionary containing:
            - status: PodcastStatus value (pending, generating, or failed)
            - podcast_id: The podcast ID for polling (when status is pending or generating)
            - title: The podcast title
            - message: Status message (or "error" field if status is failed)
        """
        try:
            # One DB session per tool call so parallel invocations never share an AsyncSession.
            async with shielded_async_session() as session:
                podcast = Podcast(
                    title=podcast_title,
                    status=PodcastStatus.PENDING,
                    search_space_id=search_space_id,
                    thread_id=thread_id,
                )
                session.add(podcast)
                await session.commit()
                await session.refresh(podcast)
                podcast_id = podcast.id

            from app.tasks.celery_tasks.podcast_tasks import (
                generate_content_podcast_task,
            )

            task = generate_content_podcast_task.delay(
                podcast_id=podcast_id,
                source_content=source_content,
                search_space_id=search_space_id,
                user_prompt=user_prompt,
            )

            print(f"[generate_podcast] Created podcast {podcast_id}, task: {task.id}")

            return {
                "status": PodcastStatus.PENDING.value,
                "podcast_id": podcast_id,
                "title": podcast_title,
                "message": "Podcast generation started. This may take a few minutes.",
            }

        except Exception as e:
            error_message = str(e)
            print(f"[generate_podcast] Error: {error_message}")
            return {
                "status": PodcastStatus.FAILED.value,
                "error": error_message,
                "title": podcast_title,
                "podcast_id": None,
            }

    return generate_podcast
