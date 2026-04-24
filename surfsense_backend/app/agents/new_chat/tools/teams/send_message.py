import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval

from ._auth import GRAPH_API, get_access_token, get_teams_connector

logger = logging.getLogger(__name__)


def create_send_teams_message_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def send_teams_message(
        team_id: str,
        channel_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Send a message to a Microsoft Teams channel.

        Requires the ChannelMessage.Send OAuth scope. If the user gets a
        permission error, they may need to re-authenticate with updated scopes.

        Args:
            team_id: The team ID (from list_teams_channels).
            channel_id: The channel ID (from list_teams_channels).
            content: The message text (HTML supported).

        Returns:
            Dictionary with status, message_id on success.

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Do NOT retry.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Teams tool not properly configured."}

        try:
            connector = await get_teams_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Teams connector found."}

            result = request_approval(
                action_type="teams_send_message",
                tool_name="send_teams_message",
                params={"team_id": team_id, "channel_id": channel_id, "content": content},
                context={"connector_id": connector.id},
            )

            if result.rejected:
                return {"status": "rejected", "message": "User declined. Message was not sent."}

            final_content = result.params.get("content", content)
            final_team = result.params.get("team_id", team_id)
            final_channel = result.params.get("channel_id", channel_id)

            token = await get_access_token(db_session, connector)

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{GRAPH_API}/teams/{final_team}/channels/{final_channel}/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"body": {"content": final_content}},
                )

            if resp.status_code == 401:
                return {"status": "auth_error", "message": "Teams token expired. Please re-authenticate.", "connector_type": "teams"}
            if resp.status_code == 403:
                return {
                    "status": "insufficient_permissions",
                    "message": "Missing ChannelMessage.Send permission. Please re-authenticate with updated scopes.",
                }
            if resp.status_code not in (200, 201):
                return {"status": "error", "message": f"Graph API error: {resp.status_code} — {resp.text[:200]}"}

            msg_data = resp.json()
            return {
                "status": "success",
                "message_id": msg_data.get("id"),
                "message": f"Message sent to Teams channel.",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error sending Teams message: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to send Teams message."}

    return send_teams_message
