"""Memory update tools backed by the canonical memory service."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.services.memory import MemoryScope, save_memory

logger = logging.getLogger(__name__)


def create_update_memory_tool(
    user_id: str | UUID,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    """Factory for the user-memory update tool.

    Uses a fresh short-lived session per call so compiled-agent caches never
    retain a stale request-scoped session.
    """
    del db_session
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the user's personal memory document.

        The current memory is shown in <user_memory>. Pass the FULL updated
        markdown document, not a diff.
        """
        try:
            async with async_session_maker() as db_session:
                result = await save_memory(
                    scope=MemoryScope.USER,
                    target_id=uid,
                    content=updated_memory,
                    session=db_session,
                    llm=llm,
                )
                return result.to_dict()
        except Exception as e:
            logger.exception("Failed to update user memory: %s", e)
            return {"status": "error", "message": f"Failed to update memory: {e}"}

    return update_memory


def create_update_team_memory_tool(
    search_space_id: int,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    """Factory for the team-memory update tool."""
    del db_session

    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the team's shared memory document for this search space.

        The current team memory is shown in <team_memory>. Pass the FULL updated
        markdown document, not a diff.
        """
        try:
            async with async_session_maker() as db_session:
                result = await save_memory(
                    scope=MemoryScope.TEAM,
                    target_id=search_space_id,
                    content=updated_memory,
                    session=db_session,
                    llm=llm,
                )
                return result.to_dict()
        except Exception as e:
            logger.exception("Failed to update team memory: %s", e)
            return {
                "status": "error",
                "message": f"Failed to update team memory: {e}",
            }

    return update_memory


__all__ = [
    "create_update_memory_tool",
    "create_update_team_memory_tool",
]
