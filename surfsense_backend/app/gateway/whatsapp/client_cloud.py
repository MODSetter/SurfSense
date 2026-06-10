"""Small httpx wrapper for the WhatsApp Cloud API."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import config
from app.gateway.base.adapter import PlatformSendResult
from app.gateway.ratelimit import wait_for_token
from app.observability.metrics import record_gateway_rate_limit_hit


class WhatsAppCloudClient:
    def __init__(
        self,
        *,
        business_token: str,
        phone_number_id: str,
        api_version: str | None = None,
    ) -> None:
        self.business_token = business_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version or config.WHATSAPP_GRAPH_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> PlatformSendResult:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": True, "body": text},
        }
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}
        data = await self._post(f"/{self.phone_number_id}/messages", json=payload)
        message_id = str((data.get("messages") or [{}])[0].get("id") or "")
        return PlatformSendResult(external_message_id=message_id, raw_response=data)

    async def send_typing_indicator(self, *, message_id: str) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"},
        }
        return await self._post(f"/{self.phone_number_id}/messages", json=payload)

    async def validate(self) -> dict[str, Any]:
        return await self._get(
            f"/{self.phone_number_id}",
            params={
                "fields": "verified_name,quality_rating,account_review_status,display_phone_number"
            },
        )

    async def _post(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.business_token}"},
                json=json,
            )
            response.raise_for_status()
            return response.json()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._throttle()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.business_token}"},
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _throttle(self) -> None:
        wait_ms = await wait_for_token(
            f"wa:phone:{self.phone_number_id}",
            capacity=10,
            refill_per_sec=10.0,
        )
        if wait_ms:
            record_gateway_rate_limit_hit(bucket="wa:phone")
