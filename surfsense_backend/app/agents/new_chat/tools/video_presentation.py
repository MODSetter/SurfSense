"""
Video presentation generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_video_presentation
tool that submits a Celery task for background video presentation generation. The
tool then polls the row until it reaches a terminal status (READY/FAILED) and
returns that status. The wait is bounded by the chat's HTTP / process lifetime;
see app.agents.shared.deliverable_wait for details.
"""

import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.deliverable_wait import wait_for_deliverable
from app.db import VideoPresentation, VideoPresentationStatus, shielded_async_session

logger = logging.getLogger(__name__)


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

            logger.info(
                "[generate_video_presentation] Created video presentation %s, task: %s",
                video_pres_id,
                task.id,
            )

            # Wait until the Celery worker flips the row to a terminal
            # state. No internal budget — see deliverable_wait module.
            terminal_status, _columns, elapsed = await wait_for_deliverable(
                model=VideoPresentation,
                row_id=video_pres_id,
                columns=[VideoPresentation.status],
                terminal_statuses={
                    VideoPresentationStatus.READY,
                    VideoPresentationStatus.FAILED,
                },
            )

            if terminal_status == VideoPresentationStatus.READY:
                logger.info(
                    "[generate_video_presentation] %s READY in %.2fs",
                    video_pres_id,
                    elapsed,
                )
                return {
                    "status": VideoPresentationStatus.READY.value,
                    "video_presentation_id": video_pres_id,
                    "title": video_title,
                    "message": "Video presentation generated and saved.",
                }

            # Only other terminal state is FAILED.
            logger.warning(
                "[generate_video_presentation] %s FAILED in %.2fs",
                video_pres_id,
                elapsed,
            )
            return {
                "status": VideoPresentationStatus.FAILED.value,
                "video_presentation_id": video_pres_id,
                "title": video_title,
                "error": (
                    "Background worker reported FAILED status for this "
                    "video presentation."
                ),
            }

        except Exception as e:
            error_message = str(e)
            logger.exception(
                "[generate_video_presentation] Error: %s", error_message
            )
            return {
                "status": VideoPresentationStatus.FAILED.value,
                "error": error_message,
                "title": video_title,
                "video_presentation_id": None,
            }

    return generate_video_presentation
