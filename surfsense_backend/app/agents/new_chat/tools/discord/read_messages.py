import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from ._auth import DISCORD_API, get_bot_token, get_discord_connector

logger = logging.getLogger(__name__)


def create_read_discord_messages_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def read_discord_messages(
        channel_id: str,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Read recent messages from a Discord text channel.

        Args:
            channel_id: The Discord channel ID (from list_discord_channels).
            limit: Number of messages to fetch (default 25, max 50).

        Returns:
            Dictionary with status and a list of messages including
            id, author, content, timestamp.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Discord tool not properly configured."}

        limit = min(limit, 50)

        try:
            connector = await get_discord_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Discord connector found."}

            token = get_bot_token(connector)

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{DISCORD_API}/channels/{channel_id}/messages",
                    headers={"Authorization": f"Bot {token}"},
                    params={"limit": limit},
                    timeout=15.0,
                )

            if resp.status_code == 401:
                return {"status": "auth_error", "message": "Discord bot token is invalid.", "connector_type": "discord"}
            if resp.status_code == 403:
                return {"status": "error", "message": "Bot lacks permission to read this channel."}
            if resp.status_code != 200:
                return {"status": "error", "message": f"Discord API error: {resp.status_code}"}

            messages = [
                {
                    "id": m["id"],
                    "author": m.get("author", {}).get("username", "Unknown"),
                    "content": m.get("content", ""),
                    "timestamp": m.get("timestamp", ""),
                }
                for m in resp.json()
            ]

            return {"status": "success", "channel_id": channel_id, "messages": messages, "total": len(messages)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error reading Discord messages: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to read Discord messages."}

    return read_discord_messages
