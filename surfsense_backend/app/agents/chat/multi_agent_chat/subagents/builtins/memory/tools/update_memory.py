"""Memory update tools backed by the canonical memory service."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memory import (
    MEMORY_HARD_LIMIT,
    MEMORY_SOFT_LIMIT,
    MemoryScope,
    save_memory,
)

logger = logging.getLogger(__name__)


def create_update_memory_tool(
    user_id: str | UUID,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the user's personal memory document.

        The current memory is shown in <user_memory>. Pass the FULL updated
        markdown document, not a diff.
        """
        try:
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
            await db_session.rollback()
            return {"status": "error", "message": f"Failed to update memory: {e}"}

    return update_memory


def create_update_team_memory_tool(
    workspace_id: int,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the team's shared memory document for this workspace.

        The current team memory is shown in <team_memory>. Pass the FULL updated
        markdown document, not a diff.
        """
        try:
            result = await save_memory(
                scope=MemoryScope.TEAM,
                target_id=workspace_id,
                content=updated_memory,
                session=db_session,
                llm=llm,
            )
            return result.to_dict()
        except Exception as e:
            logger.exception("Failed to update team memory: %s", e)
            await db_session.rollback()
            return {
                "status": "error",
                "message": f"Failed to update team memory: {e}",
            }

    return update_memory


__all__ = [
    "MEMORY_HARD_LIMIT",
    "MEMORY_SOFT_LIMIT",
    "create_update_memory_tool",
    "create_update_team_memory_tool",
]
