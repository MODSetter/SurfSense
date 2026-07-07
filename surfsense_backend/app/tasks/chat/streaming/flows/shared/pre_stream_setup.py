"""Pre-stream setup: connector service, checkpointer."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.checkpointer import get_checkpointer
from app.services.connector_service import ConnectorService


async def setup_connector_service(
    session: AsyncSession,
    *,
    workspace_id: int,
) -> ConnectorService:
    """Build the per-turn connector service for the workspace."""
    return ConnectorService(session, workspace_id=workspace_id)


async def get_chat_checkpointer():
    """Resolve the PostgreSQL checkpointer for persistent conversation memory.

    Thin wrapper around ``app.agents.chat.runtime.checkpointer.get_checkpointer`` so
    flow orchestrators can rely on a streaming-local symbol and we have a hook
    point if the checkpointer source ever needs to vary per flow.
    """
    return await get_checkpointer()
