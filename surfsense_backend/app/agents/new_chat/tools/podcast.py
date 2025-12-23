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

# Redis connection for tracking active podcast tasks
# Uses the same Redis instance as Celery
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for podcast task tracking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def get_active_podcast_key(search_space_id: int) -> str:
    """Generate Redis key for tracking active podcast task."""
    return f"podcast:active:{search_space_id}"


def get_active_podcast_task(search_space_id: int) -> str | None:
    """Check if there's an active podcast task for this search space."""
    try:
        client = get_redis_client()
        return client.get(get_active_podcast_key(search_space_id))
    except Exception:
        # If Redis is unavailable, allow the request (fail open)
        return None


def set_active_podcast_task(search_space_id: int, task_id: str) -> None:
    """Mark a podcast task as active for this search space."""
    try:
        client = get_redis_client()
        # Set with 30-minute expiry as safety net (podcast should complete before this)
        client.setex(get_active_podcast_key(search_space_id), 1800, task_id)
    except Exception as e:
        print(f"[generate_podcast] Warning: Could not set active task in Redis: {e}")


def clear_active_podcast_task(search_space_id: int) -> None:
    """Clear the active podcast task for this search space."""
    try:
        client = get_redis_client()
        client.delete(get_active_podcast_key(search_space_id))
    except Exception as e:
        print(f"[generate_podcast] Warning: Could not clear active task in Redis: {e}")


def create_generate_podcast_tool(
    search_space_id: int,
    db_session: AsyncSession,
):
    """
    Factory function to create the generate_podcast tool with injected dependencies.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session (not used - Celery creates its own)

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

        IMPORTANT: Only one podcast can be generated at a time. If a podcast
        is already being generated, this tool will return a message asking
        the user to wait.

        Args:
            source_content: The text content to convert into a podcast.
                           This can be a summary, research findings, or any text
                           the user wants transformed into an audio podcast.
            podcast_title: Title for the podcast (default: "SurfSense Podcast")
            user_prompt: Optional instructions for podcast style, tone, or format.
                        For example: "Make it casual and fun" or "Focus on the key insights"

        Returns:
            A dictionary containing:
            - status: "processing" (task submitted), "already_generating", or "error"
            - task_id: The Celery task ID for polling status (if processing)
            - title: The podcast title
            - message: Status message for the user
        """
        try:
            # Check if a podcast is already being generated for this search space
            active_task_id = get_active_podcast_task(search_space_id)
            if active_task_id:
                print(
                    f"[generate_podcast] Blocked duplicate request. Active task: {active_task_id}"
                )
                return {
                    "status": "already_generating",
                    "task_id": active_task_id,
                    "title": podcast_title,
                    "message": "A podcast is already being generated. Please wait for it to complete before requesting another one.",
                }

            # Import Celery task here to avoid circular imports
            from app.tasks.celery_tasks.podcast_tasks import (
                generate_content_podcast_task,
            )

            # Submit Celery task for background processing
            task = generate_content_podcast_task.delay(
                source_content=source_content,
                search_space_id=search_space_id,
                podcast_title=podcast_title,
                user_prompt=user_prompt,
            )

            # Mark this task as active
            set_active_podcast_task(search_space_id, task.id)

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
