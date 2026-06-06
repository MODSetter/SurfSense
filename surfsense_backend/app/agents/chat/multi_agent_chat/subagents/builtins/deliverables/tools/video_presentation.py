"""Factory for a video-presentation tool.

Dispatches the heavy generation to Celery and then polls the
video-presentation row until it reaches a terminal status (READY/FAILED).
The tool always returns a real terminal ``Receipt`` — never a pending
one. The wait is bounded by the existing per-invocation safety net
(``SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS`` in multi-agent mode,
HTTP / process lifetime in single-agent mode). Video rendering can be
heavy; raise that ceiling if your generations routinely exceed it.
"""

import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.deliverable_wait import (
    wait_for_deliverable,
)
from app.db import VideoPresentation, VideoPresentationStatus, shielded_async_session

logger = logging.getLogger(__name__)


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
        runtime: ToolRuntime,
        video_title: str = "SurfSense Presentation",
        user_prompt: str | None = None,
    ) -> Command:
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

            logger.info(
                "[generate_video_presentation] Created video presentation %s, task: %s",
                video_pres_id,
                task.id,
            )

            # Wait until the Celery worker flips the row to a terminal
            # state. The wait is bounded only by the subagent invoke
            # timeout (multi-agent) or HTTP lifetime (single-agent) —
            # see app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.deliverable_wait for details.
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
                payload: dict[str, Any] = {
                    "status": VideoPresentationStatus.READY.value,
                    "video_presentation_id": video_pres_id,
                    "title": video_title,
                    "message": "Video presentation generated and saved.",
                }
                return with_receipt(
                    payload=payload,
                    receipt=make_receipt(
                        route="deliverables",
                        type="video_presentation",
                        operation="generate",
                        status="success",
                        external_id=str(video_pres_id),
                        preview=video_title,
                    ),
                    tool_call_id=runtime.tool_call_id,
                )

            # Only other terminal state is FAILED.
            logger.warning(
                "[generate_video_presentation] %s FAILED in %.2fs",
                video_pres_id,
                elapsed,
            )
            err = (
                "Background worker reported FAILED status for this video presentation."
            )
            payload = {
                "status": VideoPresentationStatus.FAILED.value,
                "video_presentation_id": video_pres_id,
                "title": video_title,
                "error": err,
            }
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="video_presentation",
                    operation="generate",
                    status="failed",
                    external_id=str(video_pres_id),
                    preview=video_title,
                    error=err,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        except Exception as e:
            error_message = str(e)
            logger.exception("[generate_video_presentation] Error: %s", error_message)
            payload = {
                "status": VideoPresentationStatus.FAILED.value,
                "error": error_message,
                "title": video_title,
                "video_presentation_id": None,
            }
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="video_presentation",
                    operation="generate",
                    status="failed",
                    preview=video_title,
                    error=error_message,
                ),
                tool_call_id=runtime.tool_call_id,
            )

    return generate_video_presentation
