"""Slack Web API client for gateway bot operations."""

from __future__ import annotations

from typing import Any

import httpx

from app.gateway.base.adapter import PlatformSendResult

SLACK_API = "https://slack.com/api"


class SlackGatewayClient:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def api_call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{SLACK_API}/{method}",
                json=payload or {},
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            error = data.get("error", "unknown_error")
            raise RuntimeError(f"Slack API {method} failed: {error}")
        return data

    async def send_message(
        self,
        *,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> PlatformSendResult:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        data = await self.api_call("chat.postMessage", payload)
        return PlatformSendResult(
            external_message_id=str(data.get("ts", "")),
            raw_response=data,
        )

    async def update_message(
        self,
        *,
        channel: str,
        ts: str,
        text: str,
    ) -> PlatformSendResult:
        data = await self.api_call("chat.update", {"channel": channel, "ts": ts, "text": text})
        return PlatformSendResult(
            external_message_id=str(data.get("ts") or ts),
            raw_response=data,
        )

    async def validate(self) -> dict[str, Any]:
        data = await self.api_call("auth.test")
        return {
            "ok": True,
            "team_id": data.get("team_id"),
            "team": data.get("team"),
            "bot_user_id": data.get("user_id"),
            "bot_username": data.get("user"),
        }
