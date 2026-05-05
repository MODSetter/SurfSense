"""Builds Discord REST API auth headers for connector-backed tools."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType
from app.utils.oauth_security import TokenEncryption

DISCORD_API = "https://discord.com/api/v10"


async def get_discord_connector(
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> SearchSourceConnector | None:
    result = await db_session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.DISCORD_CONNECTOR,
        )
    )
    return result.scalars().first()


def get_bot_token(connector: SearchSourceConnector) -> str:
    """Extract and decrypt the bot token from connector config."""
    cfg = dict(connector.config)
    if cfg.get("_token_encrypted") and config.SECRET_KEY:
        enc = TokenEncryption(config.SECRET_KEY)
        if cfg.get("bot_token"):
            cfg["bot_token"] = enc.decrypt_token(cfg["bot_token"])
    token = cfg.get("bot_token")
    if not token:
        raise ValueError("Discord bot token not found in connector config.")
    return token


def get_guild_id(connector: SearchSourceConnector) -> str | None:
    return connector.config.get("guild_id")
