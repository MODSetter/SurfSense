"""Factory for a podcast-generation tool.

Dispatches the heavy generation to Celery and then polls the podcast row
until it reaches a terminal status (READY/FAILED). The tool always
returns a real terminal ``Receipt`` — never a pending one. The wait is
bounded by the existing per-invocation safety net
(``SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS`` in multi-agent mode,
HTTP / process lifetime in single-agent mode).
"""

import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.deliverable_wait import wait_for_deliverable
from app.agents.shared.receipt import make_receipt
from app.agents.shared.receipt_command import with_receipt
from app.db import Podcast, PodcastStatus, shielded_async_session

logger = logging.getLogger(__name__)


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
        runtime: ToolRuntime,
        podcast_title: str = "SurfSense Podcast",
        user_prompt: str | None = None,
    ) -> Command:
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

            logger.info(
                "[generate_podcast] Created podcast %s, task: %s",
                podcast_id,
                task.id,
            )

            # Wait until the Celery worker flips the row to a terminal
            # state. The wait is bounded only by the subagent invoke
            # timeout (multi-agent) or HTTP lifetime (single-agent) —
            # see app.agents.shared.deliverable_wait for details.
            terminal_status, columns, elapsed = await wait_for_deliverable(
                model=Podcast,
                row_id=podcast_id,
                columns=[Podcast.status, Podcast.file_location],
                terminal_statuses={PodcastStatus.READY, PodcastStatus.FAILED},
            )

            if terminal_status == PodcastStatus.READY:
                file_location = columns[1] if columns else None
                logger.info(
                    "[generate_podcast] Podcast %s READY in %.2fs (file=%s)",
                    podcast_id,
                    elapsed,
                    file_location,
                )
                payload: dict[str, Any] = {
                    "status": PodcastStatus.READY.value,
                    "podcast_id": podcast_id,
                    "title": podcast_title,
                    "file_location": file_location,
                    "message": ("Podcast generated and saved to your podcast panel."),
                }
                return with_receipt(
                    payload=payload,
                    receipt=make_receipt(
                        route="deliverables",
                        type="podcast",
                        operation="generate",
                        status="success",
                        external_id=str(podcast_id),
                        preview=podcast_title,
                    ),
                    tool_call_id=runtime.tool_call_id,
                )

            # Only other terminal state is FAILED.
            logger.warning(
                "[generate_podcast] Podcast %s FAILED in %.2fs",
                podcast_id,
                elapsed,
            )
            err = "Background worker reported FAILED status for this podcast."
            payload = {
                "status": PodcastStatus.FAILED.value,
                "podcast_id": podcast_id,
                "title": podcast_title,
                "error": err,
            }
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="podcast",
                    operation="generate",
                    status="failed",
                    external_id=str(podcast_id),
                    preview=podcast_title,
                    error=err,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        except Exception as e:
            error_message = str(e)
            logger.exception("[generate_podcast] Error: %s", error_message)
            payload = {
                "status": PodcastStatus.FAILED.value,
                "error": error_message,
                "title": podcast_title,
                "podcast_id": None,
            }
            receipt = make_receipt(
                route="deliverables",
                type="podcast",
                operation="generate",
                status="failed",
                preview=podcast_title,
                error=error_message,
            )
            return with_receipt(
                payload=payload,
                receipt=receipt,
                tool_call_id=runtime.tool_call_id,
            )

    return generate_podcast
