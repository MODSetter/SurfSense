"""Discord platform adapter for bot mentions and replies."""

from __future__ import annotations

import re
from typing import Any

from app.gateway.base.adapter import (
    BasePlatformAdapter,
    ParsedInboundEvent,
    PlatformSendResult,
)
from app.gateway.discord.client import DiscordGatewayClient

MENTION_RE = re.compile(r"<@!?\d+>\s*")


def discord_user_peer_id(guild_id: str, discord_user_id: str) -> str:
    return f"discord_user:{guild_id}:{discord_user_id}"


def discord_thread_peer_id(guild_id: str, channel_id: str, thread_key: str) -> str:
    return f"discord_thread:{guild_id}:{channel_id}:{thread_key}"


class DiscordAdapter(BasePlatformAdapter):
    platform = "discord"

    def __init__(self, bot_token: str, *, bot_user_id: str | None = None) -> None:
        self.bot_user_id = bot_user_id
        self.client = DiscordGatewayClient(bot_token)

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        event = raw_payload.get("event") or raw_payload
        event_kind = str(raw_payload.get("type") or event.get("type") or "message")
        guild_id = str(event.get("guild_id") or "")
        channel_id = str(event.get("channel_id") or "")
        author = event.get("author") or {}
        discord_user_id = str(author.get("id") or event.get("author_id") or "")
        message_id = str(event.get("id") or event.get("message_id") or "")
        bot_user_id = self.bot_user_id or str(raw_payload.get("bot_user_id") or "")

        if not guild_id or not channel_id or not discord_user_id or not message_id:
            return ParsedInboundEvent(
                platform=self.platform,
                event_kind=event_kind,
                external_peer_id=None,
                external_peer_kind="unknown",
                external_message_id=message_id or None,
                external_user_id=discord_user_id or None,
                text=None,
                raw_payload=raw_payload,
                metadata={
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "bot_user_id": bot_user_id,
                },
            )

        text = str(event.get("content") or "")
        if bot_user_id:
            text = text.replace(f"<@{bot_user_id}>", "")
            text = text.replace(f"<@!{bot_user_id}>", "")
        text = MENTION_RE.sub("", text).strip()

        thread_key = str(
            event.get("thread_id")
            or (event.get("message_reference") or {}).get("message_id")
            or message_id
        )
        thread_peer_id = discord_thread_peer_id(guild_id, channel_id, thread_key)
        user_peer_id = discord_user_peer_id(guild_id, discord_user_id)
        mentions = event.get("mentions") or []
        mentions_bot = bool(
            bot_user_id
            and any(str(mention.get("id")) == bot_user_id for mention in mentions)
        )

        return ParsedInboundEvent(
            platform=self.platform,
            event_kind=event_kind,
            external_peer_id=thread_peer_id,
            external_peer_kind="channel",
            external_message_id=message_id,
            external_user_id=discord_user_id,
            text=text,
            raw_payload=raw_payload,
            display_name=event.get("channel_name"),
            username=author.get("username") or discord_user_id,
            metadata={
                "guild_id": guild_id,
                "channel_id": channel_id,
                "discord_user_id": discord_user_id,
                "message_id": message_id,
                "thread_key": thread_key,
                "bot_user_id": bot_user_id,
                "discord_user_peer_id": user_peer_id,
                "discord_thread_peer_id": thread_peer_id,
                "mentions_bot": mentions_bot,
                "is_dm": False,
            },
        )

    async def send_message(
        self,
        *,
        external_peer_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> PlatformSendResult:
        del parse_mode
        return await self.client.send_message(
            channel_id=external_peer_id,
            content=text,
            reply_to_message_id=reply_to_message_id,
        )

    async def edit_message(
        self,
        *,
        external_peer_id: str,
        external_message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> PlatformSendResult:
        del parse_mode
        return await self.client.update_message(
            channel_id=external_peer_id,
            message_id=external_message_id,
            content=text,
        )

    async def validate_credentials(self) -> dict[str, Any]:
        return await self.client.validate()
