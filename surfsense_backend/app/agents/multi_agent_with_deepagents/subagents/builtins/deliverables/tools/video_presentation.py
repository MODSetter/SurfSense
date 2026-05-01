"""Factory for a video-presentation tool that queues background work and returns an ID for polling."""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import VideoPresentation, VideoPresentationStatus, shielded_async_session


def create_generate_video_presentation_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """Create ``generate_video_presentation`` with bound search space and thread; writes use a tool-local session."""
    del db_session  # writes use a fresh tool-local session, see below

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
            # One DB session per tool call so parallel invocations never share an AsyncSession.
            async with shielded_async_session() as session:
                video_pres = VideoPresentation(
                    title=video_title,
                    status=VideoPresentationStatus.PENDING,
                    search_space_id=search_space_id,
                    thread_id=thread_id,
                )
                session.add(video_pres)
                await session.commit()
                await session.refresh(video_pres)
                video_pres_id = video_pres.id

            from app.tasks.celery_tasks.video_presentation_tasks import (
                generate_video_presentation_task,
            )

            task = generate_video_presentation_task.delay(
                video_presentation_id=video_pres_id,
                source_content=source_content,
                search_space_id=search_space_id,
                user_prompt=user_prompt,
            )

            print(
                f"[generate_video_presentation] Created video presentation {video_pres_id}, task: {task.id}"
            )

            return {
                "status": VideoPresentationStatus.PENDING.value,
                "video_presentation_id": video_pres_id,
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
