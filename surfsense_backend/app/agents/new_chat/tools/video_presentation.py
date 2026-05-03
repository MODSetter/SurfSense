"""
Video presentation generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_video_presentation
tool that submits a Celery task for background video presentation generation.
The frontend polls for completion and auto-updates when the presentation is ready.
"""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import VideoPresentation, VideoPresentationStatus, shielded_async_session


def create_generate_video_presentation_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_video_presentation tool with injected dependencies.

    Pre-creates video presentation record with pending status so the ID is available
    immediately for frontend polling. The row is written via a fresh, tool-local
    session so parallel tool calls (e.g. video + podcast in the same agent step)
    don't share an ``AsyncSession`` (which is not concurrency-safe).
    """
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
            # See podcast.py for the rationale: parallel tool calls share the
            # streaming session, and AsyncSession is not concurrency-safe —
            # interleaved flushes produce "Session.add() during flush" and
            # poison the transaction for every concurrent tool.
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
