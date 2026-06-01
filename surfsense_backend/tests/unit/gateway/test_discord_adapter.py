from __future__ import annotations

import pytest

from app.gateway.base.adapter import PlatformSendResult
from app.gateway.discord.adapter import DiscordAdapter


def _discord_payload(content: str = "<@999> summarize this channel"):
    return {
        "type": "message",
        "bot_user_id": "999",
        "event": {
            "type": "message",
            "id": "111",
            "guild_id": "222",
            "guild_name": "SurfSense Guild",
            "channel_id": "333",
            "channel_name": "general",
            "content": content,
            "author": {"id": "444", "username": "anish", "bot": False},
            "mentions": [{"id": "999", "username": "SurfSense"}],
        },
    }


def test_discord_adapter_parses_mention_and_strips_bot_mention():
    adapter = DiscordAdapter("discord-token", bot_user_id="999")

    parsed = adapter.parse_inbound(_discord_payload())

    assert parsed.platform == "discord"
    assert parsed.text == "summarize this channel"
    assert parsed.external_peer_id == "discord_thread:222:333:111"
    assert parsed.metadata["discord_user_peer_id"] == "discord_user:222:444"
    assert parsed.metadata["discord_thread_peer_id"] == "discord_thread:222:333:111"
    assert parsed.metadata["mentions_bot"] is True


def test_discord_adapter_strips_nickname_mention():
    adapter = DiscordAdapter("discord-token", bot_user_id="999")

    parsed = adapter.parse_inbound(_discord_payload("<@!999> continue"))

    assert parsed.text == "continue"


def test_discord_adapter_uses_message_reference_as_thread_key():
    adapter = DiscordAdapter("discord-token", bot_user_id="999")
    payload = _discord_payload("<@999> continue")
    payload["event"]["id"] = "112"
    payload["event"]["message_reference"] = {
        "message_id": "111",
        "channel_id": "333",
        "guild_id": "222",
    }

    parsed = adapter.parse_inbound(payload)

    assert parsed.external_peer_id == "discord_thread:222:333:111"
    assert parsed.metadata["message_id"] == "112"
    assert parsed.metadata["thread_key"] == "111"


def test_discord_adapter_returns_missing_peer_for_incomplete_payload():
    adapter = DiscordAdapter("discord-token", bot_user_id="999")

    parsed = adapter.parse_inbound({"event": {"id": "111"}})

    assert parsed.external_peer_id is None
    assert parsed.external_peer_kind == "unknown"


@pytest.mark.asyncio
async def test_discord_adapter_sends_message(mocker):
    adapter = DiscordAdapter("discord-token", bot_user_id="999")
    adapter.client.send_message = mocker.AsyncMock(
        return_value=PlatformSendResult(external_message_id="555")
    )

    result = await adapter.send_message(
        external_peer_id="333",
        text="hello",
        reply_to_message_id="111",
    )

    assert result.external_message_id == "555"
    adapter.client.send_message.assert_awaited_once_with(
        channel_id="333",
        content="hello",
        reply_to_message_id="111",
    )
