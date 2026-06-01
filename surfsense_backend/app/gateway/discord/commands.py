"""Discord command/onboarding handlers."""

from __future__ import annotations

from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.base.commands import BaseGatewayCommands
from app.gateway.discord.adapter import DiscordAdapter
from app.gateway.ratelimit import acquire_token

HELP_TEXT = (
    "SurfSense Discord commands:\n"
    "`/new` - start a fresh SurfSense conversation for this Discord thread\n"
    "`/help` - show this help\n\n"
    "Mention the SurfSense bot in a Discord channel to ask your agent a question. "
    "Discord search remains controlled by the Discord connector in SurfSense."
)


class DiscordGatewayCommands(BaseGatewayCommands):
    async def handle_help_command(
        self,
        *,
        adapter: DiscordAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        channel_id = event.metadata.get("channel_id")
        message_id = event.metadata.get("message_id")
        if not channel_id:
            return True
        await adapter.send_message(
            external_peer_id=channel_id,
            text=HELP_TEXT,
            reply_to_message_id=message_id,
        )
        return True

    async def send_unbound_onboarding(
        self,
        *,
        adapter: DiscordAdapter,
        event: ParsedInboundEvent,
        dashboard_url: str,
    ) -> None:
        channel_id = event.metadata.get("channel_id")
        message_id = event.metadata.get("message_id")
        guild_id = event.metadata.get("guild_id")
        discord_user_id = event.metadata.get("discord_user_id")
        if not channel_id or not message_id:
            return

        wait_ms = await acquire_token(
            f"discord:onboarded:{guild_id}:{discord_user_id}",
            capacity=1,
            refill_per_sec=1 / 3600,
        )
        if wait_ms > 0:
            return

        await adapter.send_message(
            external_peer_id=channel_id,
            reply_to_message_id=message_id,
            text=(
                "Hi! Connect your Discord user to SurfSense before using the bot here: "
                f"{dashboard_url}"
            ),
        )
