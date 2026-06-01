"""Slack platform adapter for app mentions and threaded replies."""

from __future__ import annotations

import re
from typing import Any

from app.gateway.base.adapter import (
    BasePlatformAdapter,
    ParsedInboundEvent,
    PlatformSendResult,
)
from app.gateway.slack.client import SlackGatewayClient

MENTION_RE = re.compile(r"<@[^>]+>\s*")


def slack_user_peer_id(team_id: str, slack_user_id: str) -> str:
    return f"slack_user:{team_id}:{slack_user_id}"


def slack_thread_peer_id(team_id: str, channel_id: str, thread_ts: str) -> str:
    return f"slack_thread:{team_id}:{channel_id}:{thread_ts}"


class SlackAdapter(BasePlatformAdapter):
    platform = "slack"

    def __init__(self, bot_token: str, *, bot_user_id: str | None = None) -> None:
        self.bot_user_id = bot_user_id
        self.client = SlackGatewayClient(bot_token)

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        event = raw_payload.get("event") or {}
        event_type = str(event.get("type") or "other")
        team_id = str(raw_payload.get("team_id") or event.get("team") or "")
        channel_id = str(event.get("channel") or "")
        slack_user_id = str(event.get("user") or "")
        message_ts = str(event.get("ts") or "")
        thread_ts = str(event.get("thread_ts") or message_ts)
        bot_user_id = self.bot_user_id or str(raw_payload.get("authorizations", [{}])[0].get("user_id") or "")

        if not channel_id or not slack_user_id or not message_ts:
            return ParsedInboundEvent(
                platform=self.platform,
                event_kind=event_type,
                external_peer_id=None,
                external_peer_kind="unknown",
                external_message_id=message_ts or None,
                external_user_id=slack_user_id or None,
                text=None,
                raw_payload=raw_payload,
                metadata={"team_id": team_id, "bot_user_id": bot_user_id},
            )

        text = str(event.get("text") or "")
        if bot_user_id:
            text = text.replace(f"<@{bot_user_id}>", "")
        text = MENTION_RE.sub("", text).strip()

        peer_kind = "direct" if str(event.get("channel_type")) == "im" else "channel"
        thread_key = slack_thread_peer_id(team_id, channel_id, thread_ts)
        user_key = slack_user_peer_id(team_id, slack_user_id)

        return ParsedInboundEvent(
            platform=self.platform,
            event_kind=event_type,
            external_peer_id=thread_key,
            external_peer_kind=peer_kind,
            external_message_id=message_ts,
            external_user_id=slack_user_id,
            text=text,
            raw_payload=raw_payload,
            display_name=None,
            username=slack_user_id,
            metadata={
                "team_id": team_id,
                "channel_id": channel_id,
                "slack_user_id": slack_user_id,
                "message_ts": message_ts,
                "thread_ts": thread_ts,
                "bot_user_id": bot_user_id,
                "slack_user_peer_id": user_key,
                "slack_thread_peer_id": thread_key,
                "channel_type": event.get("channel_type"),
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
            channel=external_peer_id,
            text=text,
            thread_ts=reply_to_message_id,
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
            channel=external_peer_id,
            ts=external_message_id,
            text=text,
        )

    async def validate_credentials(self) -> dict[str, Any]:
        return await self.client.validate()
