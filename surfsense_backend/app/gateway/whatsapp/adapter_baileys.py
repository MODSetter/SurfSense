"""Baileys bridge platform adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import config
from app.gateway.base.adapter import (
    BasePlatformAdapter,
    ParsedInboundEvent,
    PlatformSendResult,
)


class WhatsAppBaileysAdapter(BasePlatformAdapter):
    platform = "whatsapp"

    def __init__(self, bridge_url: str | None = None) -> None:
        self.bridge_url = (bridge_url or config.WHATSAPP_BRIDGE_URL).rstrip("/")

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        chat_id = str(raw_payload.get("chatId") or "")
        sender_id = str(raw_payload.get("senderId") or chat_id)
        message_id = str(raw_payload.get("messageId") or "")
        body = raw_payload.get("body")
        is_group = bool(raw_payload.get("isGroup"))
        return ParsedInboundEvent(
            platform=self.platform,
            event_kind="message",
            external_peer_id=chat_id or None,
            external_peer_kind="group" if is_group else "direct",
            external_message_id=message_id or None,
            external_user_id=sender_id or None,
            text=str(body) if body is not None else None,
            raw_payload=raw_payload,
            display_name=str(raw_payload.get("chatName") or sender_id or chat_id) or None,
            username=None,
            metadata={
                "sender_id": sender_id,
                "from_me": bool(raw_payload.get("fromMe")),
                "timestamp": raw_payload.get("timestamp"),
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
        payload: dict[str, Any] = {"chatId": external_peer_id, "message": text}
        if reply_to_message_id:
            payload["replyTo"] = reply_to_message_id
        data = await self._post("/send", payload)
        return PlatformSendResult(
            external_message_id=str(data.get("messageId") or ""),
            raw_response=data,
        )

    async def edit_message(
        self,
        *,
        external_peer_id: str,
        external_message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> PlatformSendResult:
        data = await self._post(
            "/edit",
            {
                "chatId": external_peer_id,
                "messageId": external_message_id,
                "message": text,
            },
        )
        return PlatformSendResult(
            external_message_id=str(data.get("messageId") or external_message_id),
            raw_response=data,
        )

    async def send_typing_indicator(self, *, external_peer_id: str) -> None:
        await self._post("/typing", {"chatId": external_peer_id}, expect_json=False)

    async def validate_credentials(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.bridge_url}/health")
            response.raise_for_status()
            return response.json()

    async def fetch_updates(self, *, offset: int | None) -> AsyncIterator[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.get(f"{self.bridge_url}/messages")
            response.raise_for_status()
            for message in response.json():
                if isinstance(message, dict):
                    yield message

    async def request_pairing_code(self, *, phone_number: str) -> dict[str, Any]:
        return await self._post("/pair", {"phoneNumber": phone_number})

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.bridge_url}{path}", json=payload)
            response.raise_for_status()
            if not expect_json or response.status_code == 204:
                return {}
            return response.json()
