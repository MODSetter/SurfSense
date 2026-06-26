"""Pre-stream setup: connector service, firecrawl key, checkpointer."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.checkpointer import get_checkpointer
from app.db import SearchSourceConnectorType
from app.services.connector_service import ConnectorService


async def setup_connector_and_firecrawl(
    session: AsyncSession,
    *,
    workspace_id: int,
) -> tuple[ConnectorService, str | None]:
    """Build the per-turn connector service and pull the firecrawl API key.

    Returns ``(connector_service, firecrawl_api_key)``. ``firecrawl_api_key`` is
    ``None`` when no web-crawler connector is configured (the agent simply
    skips firecrawl-backed tools in that case).
    """
    connector_service = ConnectorService(session, workspace_id=workspace_id)
    firecrawl_api_key: str | None = None
    webcrawler_connector = await connector_service.get_connector_by_type(
        SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, workspace_id
    )
    if webcrawler_connector and webcrawler_connector.config:
        firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")
    return connector_service, firecrawl_api_key


async def get_chat_checkpointer():
    """Resolve the PostgreSQL checkpointer for persistent conversation memory.

    Thin wrapper around ``app.agents.chat.runtime.checkpointer.get_checkpointer`` so
    flow orchestrators can rely on a streaming-local symbol and we have a hook
    point if the checkpointer source ever needs to vary per flow.
    """
    return await get_checkpointer()
