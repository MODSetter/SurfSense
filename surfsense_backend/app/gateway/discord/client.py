"""Discord REST API client for gateway bot operations."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.gateway.base.adapter import PlatformSendResult

DISCORD_API = "https://discord.com/api/v10"


class DiscordGatewayClient:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def api_call(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_rate_limit: bool = True,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(
                method,
                f"{DISCORD_API}{path}",
                json=payload,
                params=params,
                headers={
                    "Authorization": f"Bot {self.bot_token}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code == 429 and retry_rate_limit:
            data = response.json()
            retry_after = float(data.get("retry_after") or 1.0)
            await asyncio.sleep(min(retry_after, 5.0))
            return await self.api_call(
                method,
                path,
                payload=payload,
                params=params,
                retry_rate_limit=False,
            )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str,
        reply_to_message_id: str | None = None,
    ) -> PlatformSendResult:
        payload: dict[str, Any] = {
            "content": content,
            "allowed_mentions": {"parse": []},
        }
        if reply_to_message_id:
            payload["message_reference"] = {
                "message_id": reply_to_message_id,
                "channel_id": channel_id,
                "fail_if_not_exists": False,
            }
        data = await self.api_call(
            "POST",
            f"/channels/{channel_id}/messages",
            payload=payload,
        )
        return PlatformSendResult(
            external_message_id=str(data.get("id", "")),
            raw_response=data,
        )

    async def update_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> PlatformSendResult:
        data = await self.api_call(
            "PATCH",
            f"/channels/{channel_id}/messages/{message_id}",
            payload={"content": content, "allowed_mentions": {"parse": []}},
        )
        return PlatformSendResult(
            external_message_id=str(data.get("id") or message_id),
            raw_response=data,
        )

    async def validate(self) -> dict[str, Any]:
        data = await self.api_call("GET", "/users/@me")
        return {
            "ok": True,
            "bot_user_id": data.get("id"),
            "bot_username": data.get("username"),
            "global_name": data.get("global_name"),
        }

    async def get_guild(self, guild_id: str) -> dict[str, Any]:
        return await self.api_call("GET", f"/guilds/{guild_id}")
