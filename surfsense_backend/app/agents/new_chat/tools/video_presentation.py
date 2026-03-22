"""
Video presentation generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_video_presentation
tool that submits a Celery task for background video presentation generation.
The frontend polls for completion and auto-updates when the presentation is ready.

Duplicate request prevention:
- Only one video presentation can be generated at a time per search space
- Uses Redis to track active video presentation tasks
- Validates the Redis marker against actual DB status to avoid stale locks
"""

from typing import Any

import redis
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import VideoPresentation, VideoPresentationStatus

REDIS_URL = config.REDIS_APP_URL
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for video presentation task tracking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _redis_key(search_space_id: int) -> str:
    return f"video_presentation:generating:{search_space_id}"


def get_generating_video_presentation_id(search_space_id: int) -> int | None:
    """Get the video presentation ID currently being generated for this search space."""
    try:
        client = get_redis_client()
        value = client.get(_redis_key(search_space_id))
        return int(value) if value else None
    except Exception:
        return None


def clear_generating_video_presentation(search_space_id: int) -> None:
    """Clear the generating marker (used when we detect a stale lock)."""
    try:
        client = get_redis_client()
        client.delete(_redis_key(search_space_id))
    except Exception:
        pass


def set_generating_video_presentation(
    search_space_id: int, video_presentation_id: int
) -> None:
    """Mark a video presentation as currently generating for this search space."""
    try:
        client = get_redis_client()
        client.setex(_redis_key(search_space_id), 1800, str(video_presentation_id))
    except Exception as e:
        print(
            f"[generate_video_presentation] Warning: Could not set generating video presentation in Redis: {e}"
        )


def create_generate_video_presentation_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_video_presentation tool with injected dependencies.

    Pre-creates video presentation record with pending status so the ID is available
    immediately for frontend polling.
    """

    @tool
    async def generate_video_presentation(
        source_content: str,
        video_title: str = "SurfSense Presentation",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a video presentation from the provided content.

        Use this tool when the user asks to create a video, presentation, slides, or slide deck.

        Args:
            source_content: The text content to turn into a presentation.
            video_title: Title for the presentation (default: "SurfSense Presentation")
            user_prompt: Optional style/tone instructions.
        """
        try:
            generating_id = get_generating_video_presentation_id(search_space_id)
            if generating_id:
                result = await db_session.execute(
                    select(VideoPresentation).filter(
                        VideoPresentation.id == generating_id
                    )
                )
                existing = result.scalars().first()

                if existing and existing.status == VideoPresentationStatus.GENERATING:
                    print(
                        f"[generate_video_presentation] Blocked duplicate — "
                        f"presentation {generating_id} is actively generating"
                    )
                    return {
                        "status": VideoPresentationStatus.GENERATING.value,
                        "video_presentation_id": generating_id,
                        "title": video_title,
                        "message": "A video presentation is already being generated. Please wait for it to complete.",
                    }

                print(
                    f"[generate_video_presentation] Stale Redis lock for presentation {generating_id} "
                    f"(status={existing.status if existing else 'not found'}). Clearing and proceeding."
                )
                clear_generating_video_presentation(search_space_id)

            video_pres = VideoPresentation(
                title=video_title,
                status=VideoPresentationStatus.PENDING,
                search_space_id=search_space_id,
                thread_id=thread_id,
            )
            db_session.add(video_pres)
            await db_session.commit()
            await db_session.refresh(video_pres)

            from app.tasks.celery_tasks.video_presentation_tasks import (
                generate_video_presentation_task,
            )

            task = generate_video_presentation_task.delay(
                video_presentation_id=video_pres.id,
                source_content=source_content,
                search_space_id=search_space_id,
                user_prompt=user_prompt,
            )

            set_generating_video_presentation(search_space_id, video_pres.id)

            print(
                f"[generate_video_presentation] Created video presentation {video_pres.id}, task: {task.id}"
            )

            return {
                "status": VideoPresentationStatus.PENDING.value,
                "video_presentation_id": video_pres.id,
                "title": video_title,
                "message": "Video presentation generation started. This may take a few minutes.",
            }

        except Exception as e:
            error_message = str(e)
            print(f"[generate_video_presentation] Error: {error_message}")
            return {
                "status": VideoPresentationStatus.FAILED.value,
                "error": error_message,
                "title": video_title,
                "video_presentation_id": None,
            }

    return generate_video_presentation
