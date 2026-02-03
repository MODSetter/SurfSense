"""
Podcast generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_podcast tool
that submits a Celery task for background podcast generation. The frontend
polls for completion and auto-updates when the podcast is ready.

Duplicate request prevention:
- Only one podcast can be generated at a time per search space
- Uses Redis to track active podcast tasks
- Returns a friendly message if a podcast is already being generated
"""

import os
from typing import Any

import redis
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Podcast, PodcastStatus

# Redis connection for tracking active podcast tasks
# Defaults to the Celery broker when REDIS_APP_URL is not set
REDIS_URL = os.getenv(
    "REDIS_APP_URL",
    os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
)
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for podcast task tracking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _redis_key(search_space_id: int) -> str:
    return f"podcast:generating:{search_space_id}"


def get_generating_podcast_id(search_space_id: int) -> int | None:
    """Get the podcast ID currently being generated for this search space."""
    try:
        client = get_redis_client()
        value = client.get(_redis_key(search_space_id))
        return int(value) if value else None
    except Exception:
        return None


def set_generating_podcast(search_space_id: int, podcast_id: int) -> None:
    """Mark a podcast as currently generating for this search space."""
    try:
        client = get_redis_client()
        client.setex(_redis_key(search_space_id), 1800, str(podcast_id))
    except Exception as e:
        print(
            f"[generate_podcast] Warning: Could not set generating podcast in Redis: {e}"
        )


def create_generate_podcast_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_podcast tool with injected dependencies.

    Pre-creates podcast record with pending status so podcast_id is available
    immediately for frontend polling.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for creating the podcast record
        thread_id: The chat thread ID for associating the podcast

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
            generating_podcast_id = get_generating_podcast_id(search_space_id)
            if generating_podcast_id:
                print(
                    f"[generate_podcast] Blocked duplicate request. Generating podcast: {generating_podcast_id}"
                )
                return {
                    "status": PodcastStatus.GENERATING.value,
                    "podcast_id": generating_podcast_id,
                    "title": podcast_title,
                    "message": "A podcast is already being generated. Please wait for it to complete.",
                }

            podcast = Podcast(
                title=podcast_title,
                status=PodcastStatus.PENDING,
                search_space_id=search_space_id,
                thread_id=thread_id,
            )
            db_session.add(podcast)
            await db_session.commit()
            await db_session.refresh(podcast)

            from app.tasks.celery_tasks.podcast_tasks import (
                generate_content_podcast_task,
            )

            task = generate_content_podcast_task.delay(
                podcast_id=podcast.id,
                source_content=source_content,
                search_space_id=search_space_id,
                user_prompt=user_prompt,
            )

            set_generating_podcast(search_space_id, podcast.id)

            print(f"[generate_podcast] Created podcast {podcast.id}, task: {task.id}")

            return {
                "status": PodcastStatus.PENDING.value,
                "podcast_id": podcast.id,
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
