"""Slack command/onboarding handlers."""

from __future__ import annotations

from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.base.commands import BaseGatewayCommands
from app.gateway.ratelimit import acquire_token
from app.gateway.slack.adapter import SlackAdapter

HELP_TEXT = (
    "SurfSense Slack commands:\n"
    "`/new` - start a fresh SurfSense conversation in this thread\n"
    "`/help` - show this help\n\n"
    "Mention the SurfSense bot in a channel thread to ask your agent a question."
)


class SlackGatewayCommands(BaseGatewayCommands):
    async def handle_help_command(
        self,
        *,
        adapter: SlackAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        channel_id = event.metadata.get("channel_id")
        thread_ts = event.metadata.get("thread_ts")
        if not channel_id or not thread_ts:
            return True
        await adapter.send_message(
            external_peer_id=channel_id,
            text=HELP_TEXT,
            reply_to_message_id=thread_ts,
        )
        return True

    async def send_unbound_onboarding(
        self,
        *,
        adapter: SlackAdapter,
        event: ParsedInboundEvent,
        dashboard_url: str,
    ) -> None:
        channel_id = event.metadata.get("channel_id")
        thread_ts = event.metadata.get("thread_ts")
        slack_user_id = event.metadata.get("slack_user_id")
        if not channel_id or not thread_ts:
            return

        wait_ms = await acquire_token(
            f"slack:onboarded:{event.metadata.get('team_id')}:{slack_user_id}",
            capacity=1,
            refill_per_sec=1 / 3600,
        )
        if wait_ms > 0:
            return

        await adapter.send_message(
            external_peer_id=channel_id,
            reply_to_message_id=thread_ts,
            text=(
                "Hi! Connect your Slack user to SurfSense before using the bot here: "
                f"{dashboard_url}"
            ),
        )
