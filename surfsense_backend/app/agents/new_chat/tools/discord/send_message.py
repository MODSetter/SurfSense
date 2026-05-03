import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.db import async_session_maker

from ._auth import DISCORD_API, get_bot_token, get_discord_connector

logger = logging.getLogger(__name__)


def create_send_discord_message_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    """
    Factory function to create the send_discord_message tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker` so the closure is safe to share across
    HTTP requests by the compiled-agent cache. Capturing a per-request
    session here would surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.

    Returns:
        Configured send_discord_message tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def send_discord_message(
        channel_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Send a message to a Discord text channel.

        Args:
            channel_id: The Discord channel ID (from list_discord_channels).
            content: The message text (max 2000 characters).

        Returns:
            Dictionary with status, message_id on success.

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Do NOT retry.
        """
        if search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Discord tool not properly configured.",
            }

        if len(content) > 2000:
            return {
                "status": "error",
                "message": "Message exceeds Discord's 2000-character limit.",
            }

        try:
            async with async_session_maker() as db_session:
                connector = await get_discord_connector(
                    db_session, search_space_id, user_id
                )
                if not connector:
                    return {"status": "error", "message": "No Discord connector found."}

                result = request_approval(
                    action_type="discord_send_message",
                    tool_name="send_discord_message",
                    params={"channel_id": channel_id, "content": content},
                    context={"connector_id": connector.id},
                )

                if result.rejected:
                    return {
                        "status": "rejected",
                        "message": "User declined. Message was not sent.",
                    }

                final_content = result.params.get("content", content)
                final_channel = result.params.get("channel_id", channel_id)

                token = get_bot_token(connector)

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{DISCORD_API}/channels/{final_channel}/messages",
                        headers={
                            "Authorization": f"Bot {token}",
                            "Content-Type": "application/json",
                        },
                        json={"content": final_content},
                        timeout=15.0,
                    )

                if resp.status_code == 401:
                    return {
                        "status": "auth_error",
                        "message": "Discord bot token is invalid.",
                        "connector_type": "discord",
                    }
                if resp.status_code == 403:
                    return {
                        "status": "error",
                        "message": "Bot lacks permission to send messages in this channel.",
                    }
                if resp.status_code not in (200, 201):
                    return {
                        "status": "error",
                        "message": f"Discord API error: {resp.status_code}",
                    }

                msg_data = resp.json()
                return {
                    "status": "success",
                    "message_id": msg_data.get("id"),
                    "message": f"Message sent to channel {final_channel}.",
                }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error sending Discord message: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to send Discord message."}

    return send_discord_message
