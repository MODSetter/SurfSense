import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from ._auth import GRAPH_API, get_access_token, get_teams_connector

logger = logging.getLogger(__name__)


def create_read_teams_messages_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def read_teams_messages(
        team_id: str,
        channel_id: str,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Read recent messages from a Microsoft Teams channel.

        Args:
            team_id: The team ID (from list_teams_channels).
            channel_id: The channel ID (from list_teams_channels).
            limit: Number of messages to fetch (default 25, max 50).

        Returns:
            Dictionary with status and a list of messages including
            id, sender, content, timestamp.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Teams tool not properly configured."}

        limit = min(limit, 50)

        try:
            connector = await get_teams_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Teams connector found."}

            token = await get_access_token(db_session, connector)

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{GRAPH_API}/teams/{team_id}/channels/{channel_id}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$top": limit},
                )

            if resp.status_code == 401:
                return {"status": "auth_error", "message": "Teams token expired. Please re-authenticate.", "connector_type": "teams"}
            if resp.status_code == 403:
                return {"status": "error", "message": "Insufficient permissions to read this channel."}
            if resp.status_code != 200:
                return {"status": "error", "message": f"Graph API error: {resp.status_code}"}

            raw_msgs = resp.json().get("value", [])
            messages = []
            for m in raw_msgs:
                sender = m.get("from", {})
                user_info = sender.get("user", {}) if sender else {}
                body = m.get("body", {})
                messages.append({
                    "id": m.get("id"),
                    "sender": user_info.get("displayName", "Unknown"),
                    "content": body.get("content", ""),
                    "content_type": body.get("contentType", "text"),
                    "timestamp": m.get("createdDateTime", ""),
                })

            return {
                "status": "success",
                "team_id": team_id,
                "channel_id": channel_id,
                "messages": messages,
                "total": len(messages),
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error reading Teams messages: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to read Teams messages."}

    return read_teams_messages
