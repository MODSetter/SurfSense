"""Markdown-document memory tool for the SurfSense agent.

Replaces the old row-per-fact save_memory / recall_memory tools with a single
update_memory tool that overwrites a freeform markdown TEXT column.  The LLM
always sees the current memory in <user_memory> / <team_memory> tags injected
by MemoryInjectionMiddleware, so it passes the FULL updated document each time.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User

logger = logging.getLogger(__name__)

MEMORY_SOFT_LIMIT = 20_000
MEMORY_HARD_LIMIT = 25_000


def _validate_memory_size(content: str) -> dict[str, Any] | None:
    """Return an error/warning dict if *content* is too large, else None."""
    length = len(content)
    if length > MEMORY_HARD_LIMIT:
        return {
            "status": "error",
            "message": (
                f"Memory exceeds {MEMORY_HARD_LIMIT:,} character limit "
                f"({length:,} chars). Consolidate by merging related items, "
                "removing outdated entries, and shortening descriptions. "
                "Then call update_memory again."
            ),
        }
    return None


def _soft_warning(content: str) -> str | None:
    """Return a warning string if content exceeds the soft limit."""
    length = len(content)
    if length > MEMORY_SOFT_LIMIT:
        return (
            f"Memory is at {length:,}/{MEMORY_HARD_LIMIT:,} characters. "
            "Consolidate by merging related items and removing less important "
            "entries on your next update."
        )
    return None


def create_update_memory_tool(
    user_id: str | UUID,
    db_session: AsyncSession,
):
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the user's personal memory document.

        Your current memory is shown in <user_memory> in the system prompt.
        When the user shares important long-term information (preferences,
        facts, instructions, context), rewrite the memory document to include
        the new information.  Merge new facts with existing ones, update
        contradictions, remove outdated entries, and keep it concise.

        Args:
            updated_memory: The FULL updated markdown document (not a diff).
        """
        error = _validate_memory_size(updated_memory)
        if error:
            return error

        try:
            result = await db_session.execute(
                select(User).where(User.id == uid)
            )
            user = result.scalars().first()
            if not user:
                return {"status": "error", "message": "User not found."}

            user.memory_md = updated_memory
            await db_session.commit()

            resp: dict[str, Any] = {
                "status": "saved",
                "message": "Memory updated.",
            }
            warning = _soft_warning(updated_memory)
            if warning:
                resp["warning"] = warning
            return resp
        except Exception as e:
            logger.exception("Failed to update user memory: %s", e)
            await db_session.rollback()
            return {
                "status": "error",
                "message": f"Failed to update memory: {e}",
            }

    return update_memory


def create_update_team_memory_tool(
    search_space_id: int,
    db_session: AsyncSession,
):
    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the team's shared memory document for this search space.

        Your current team memory is shown in <team_memory> in the system
        prompt.  When the team shares important long-term information
        (decisions, conventions, key facts, priorities), rewrite the memory
        document to include the new information.  Merge new facts with
        existing ones, update contradictions, remove outdated entries, and
        keep it concise.

        Args:
            updated_memory: The FULL updated markdown document (not a diff).
        """
        error = _validate_memory_size(updated_memory)
        if error:
            return error

        try:
            result = await db_session.execute(
                select(SearchSpace).where(SearchSpace.id == search_space_id)
            )
            space = result.scalars().first()
            if not space:
                return {"status": "error", "message": "Search space not found."}

            space.shared_memory_md = updated_memory
            await db_session.commit()

            resp: dict[str, Any] = {
                "status": "saved",
                "message": "Team memory updated.",
            }
            warning = _soft_warning(updated_memory)
            if warning:
                resp["warning"] = warning
            return resp
        except Exception as e:
            logger.exception("Failed to update team memory: %s", e)
            await db_session.rollback()
            return {
                "status": "error",
                "message": f"Failed to update team memory: {e}",
            }

    return update_memory
