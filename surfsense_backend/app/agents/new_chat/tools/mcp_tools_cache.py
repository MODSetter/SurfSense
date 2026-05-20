"""Persist MCP ``list_tools`` results in ``SearchSourceConnector.config.cached_tools``."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import SearchSourceConnector, async_session_maker

logger = logging.getLogger(__name__)


class CachedMCPToolDef(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class CachedMCPTools(BaseModel):
    discovered_at: datetime
    server_version: str | None = None
    server_name: str | None = None
    transport: str | None = None
    tools: list[CachedMCPToolDef]


def read_cached_tools(connector: SearchSourceConnector) -> CachedMCPTools | None:
    """Return parsed cached tools or ``None`` if missing / corrupt (caller falls back to live discovery)."""
    cfg = connector.config or {}
    raw = cfg.get("cached_tools")
    if not raw or not isinstance(raw, dict):
        return None

    try:
        return CachedMCPTools.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "MCP connector %d has corrupt cached_tools — falling back to live discovery: %s",
            connector.id,
            exc,
        )
        return None


async def write_cached_tools(
    connector_id: int,
    tool_definitions: list[dict[str, Any]],
    *,
    server_name: str | None = None,
    server_version: str | None = None,
    transport: str | None = None,
) -> None:
    """Best-effort persist; uses its own session so a write failure cannot poison the caller's transaction."""
    payload = CachedMCPTools(
        discovered_at=datetime.now(UTC),
        server_version=server_version,
        server_name=server_name,
        transport=transport,
        tools=[CachedMCPToolDef.model_validate(td) for td in tool_definitions],
    )

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                )
            )
            connector = result.scalars().first()
            if connector is None:
                return

            cfg = dict(connector.config or {})
            cfg["cached_tools"] = payload.model_dump(mode="json")
            connector.config = cfg
            flag_modified(connector, "config")
            await session.commit()

            logger.info(
                "Persisted cached_tools for MCP connector %d (%d tools)",
                connector_id,
                len(payload.tools),
            )
    except Exception:
        logger.warning(
            "Failed to persist cached_tools for MCP connector %d",
            connector_id,
            exc_info=True,
        )
