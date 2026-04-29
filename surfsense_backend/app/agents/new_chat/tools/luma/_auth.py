"""Shared auth helper for Luma agent tools."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSourceConnector, SearchSourceConnectorType

LUMA_API = "https://public-api.luma.com/v1"


async def get_luma_connector(
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> SearchSourceConnector | None:
    result = await db_session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.LUMA_CONNECTOR,
        )
    )
    return result.scalars().first()


def get_api_key(connector: SearchSourceConnector) -> str:
    """Extract the API key from connector config (handles both key names)."""
    key = connector.config.get("api_key") or connector.config.get("LUMA_API_KEY")
    if not key:
        raise ValueError("Luma API key not found in connector config.")
    return key


def luma_headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-luma-api-key": api_key,
    }
