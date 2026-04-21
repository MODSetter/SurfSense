"""Shared auth helper for Teams agent tools (Microsoft Graph REST API)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"


async def get_teams_connector(
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> SearchSourceConnector | None:
    result = await db_session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.TEAMS_CONNECTOR,
        )
    )
    return result.scalars().first()


async def get_access_token(
    db_session: AsyncSession,
    connector: SearchSourceConnector,
) -> str:
    """Get a valid Microsoft Graph access token, refreshing if expired."""
    from app.connectors.teams_connector import TeamsConnector

    tc = TeamsConnector(
        session=db_session,
        connector_id=connector.id,
    )
    return await tc._get_valid_token()
