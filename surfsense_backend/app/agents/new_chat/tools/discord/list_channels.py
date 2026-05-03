import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker

from ._auth import DISCORD_API, get_bot_token, get_discord_connector, get_guild_id

logger = logging.getLogger(__name__)


def create_list_discord_channels_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    """
    Factory function to create the list_discord_channels tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker` so the closure is safe to share across
    HTTP requests by the compiled-agent cache. Capturing a per-request
    session here would surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.

    Returns:
        Configured list_discord_channels tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def list_discord_channels() -> dict[str, Any]:
        """List text channels in the connected Discord server.

        Returns:
            Dictionary with status and a list of channels (id, name).
        """
        if search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Discord tool not properly configured.",
            }

        try:
            async with async_session_maker() as db_session:
                connector = await get_discord_connector(
                    db_session, search_space_id, user_id
                )
                if not connector:
                    return {"status": "error", "message": "No Discord connector found."}

                guild_id = get_guild_id(connector)
                if not guild_id:
                    return {
                        "status": "error",
                        "message": "No guild ID in Discord connector config.",
                    }

                token = get_bot_token(connector)

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{DISCORD_API}/guilds/{guild_id}/channels",
                        headers={"Authorization": f"Bot {token}"},
                        timeout=15.0,
                    )

                if resp.status_code == 401:
                    return {
                        "status": "auth_error",
                        "message": "Discord bot token is invalid.",
                        "connector_type": "discord",
                    }
                if resp.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"Discord API error: {resp.status_code}",
                    }

                # Type 0 = text channel
                channels = [
                    {"id": ch["id"], "name": ch["name"]}
                    for ch in resp.json()
                    if ch.get("type") == 0
                ]
                return {
                    "status": "success",
                    "guild_id": guild_id,
                    "channels": channels,
                    "total": len(channels),
                }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error listing Discord channels: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to list Discord channels."}

    return list_discord_channels
