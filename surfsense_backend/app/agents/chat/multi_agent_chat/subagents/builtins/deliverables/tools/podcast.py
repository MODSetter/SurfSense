"""Factory for a podcast-generation tool.

Creates the podcast and proposes its brief (language, voices, length) inline,
then returns immediately with the row awaiting review. Everything after —
brief approval, drafting, rendering — happens on the live podcast card, so
this tool never blocks on generation and the chat text must not describe a
status that the card will outgrow.
"""

import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    resolve_root_thread_id,
)
from app.db import PodcastStatus, shielded_async_session
from app.podcasts.generation.brief import propose_brief
from app.podcasts.service import PodcastService

logger = logging.getLogger(__name__)


def create_generate_podcast_tool(
    workspace_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """Create ``generate_podcast`` with bound workspace and thread; DB writes use a tool-local session."""
    del db_session  # writes use a fresh tool-local session, see below

    @tool
    async def generate_podcast(
        source_content: str,
        runtime: ToolRuntime,
        podcast_title: str = "SurfSense Podcast",
        user_prompt: str | None = None,
    ) -> Command:
        """
        Prepare a podcast from the provided content for the user to review.

        Use this tool when the user asks to create, generate, or make a podcast.
        Common triggers include phrases like:
        - "Give me a podcast about this"
        - "Create a podcast from this conversation"
        - "Generate a podcast summary"
        - "Make a podcast about..."
        - "Turn this into a podcast"

        This sets up the podcast and proposes its brief (language, voices,
        length). The user reviews the brief on the live podcast card in the
        chat; after approval the episode drafts and renders automatically.
        Generation does not start here, and the card tracks all progress — do
        not describe the podcast's current status in your reply.

        Args:
            source_content: The text content to convert into a podcast.
            podcast_title: Title for the podcast (default: "SurfSense Podcast")
            user_prompt: Optional steer for what the episode should focus on.

        Returns:
            A dictionary containing:
            - status: the podcast lifecycle status (awaiting_brief on success)
            - podcast_id: the podcast ID to review in the panel
            - title: the podcast title
            - message: what the user should do next (or "error" when failed)
        """
        try:
            # One DB session per tool call so parallel invocations never share an AsyncSession.
            async with shielded_async_session() as session:
                service = PodcastService(session)
                podcast = await service.create(
                    title=podcast_title,
                    workspace_id=workspace_id,
                    thread_id=resolve_root_thread_id(runtime, thread_id),
                )
                podcast.source_content = source_content
                spec = await propose_brief(
                    session,
                    workspace_id=workspace_id,
                    focus=user_prompt,
                )
                await service.attach_brief(podcast, spec)
                await session.commit()
                podcast_id = podcast.id

            logger.info(
                "[generate_podcast] Prepared podcast %s awaiting brief review",
                podcast_id,
            )

            payload: dict[str, Any] = {
                "status": PodcastStatus.AWAITING_BRIEF.value,
                "podcast_id": podcast_id,
                "title": podcast_title,
                "message": (
                    "Podcast set up. The card in the chat handles the rest: "
                    "the user reviews the brief (language, voices, length) "
                    "there, and the episode drafts and renders automatically "
                    "after approval. The card tracks progress live, so do not "
                    "state the podcast's current status in your reply."
                ),
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
