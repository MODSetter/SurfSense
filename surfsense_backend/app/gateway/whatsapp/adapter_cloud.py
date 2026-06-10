"""WhatsApp Cloud API platform adapter."""

from __future__ import annotations

from typing import Any

from app.gateway.base.adapter import (
    BasePlatformAdapter,
    ParsedInboundEvent,
    PlatformSendResult,
)
from app.gateway.whatsapp.client_cloud import WhatsAppCloudClient
from app.gateway.whatsapp.credentials import WhatsAppCredentials


class WhatsAppCloudAdapter(BasePlatformAdapter):
    platform = "whatsapp"

    def __init__(self, credentials: WhatsAppCredentials) -> None:
        self.credentials = credentials
        self.client = WhatsAppCloudClient(
            business_token=credentials["business_token"],
            phone_number_id=credentials["phone_number_id"],
            api_version=credentials.get("api_version"),
        )

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        message = _first_message(raw_payload)
        if message is None:
            return ParsedInboundEvent(
                platform=self.platform,
                event_kind="other",
                external_peer_id=None,
                external_peer_kind="unknown",
                external_message_id=None,
                external_user_id=None,
                text=None,
                raw_payload=raw_payload,
            )

        contact = _first_contact(raw_payload, message.get("from"))
        text = _message_text(message)
        wa_id = str(message.get("from") or "")
        return ParsedInboundEvent(
            platform=self.platform,
            event_kind=str(message.get("type") or "message"),
            external_peer_id=wa_id or None,
            external_peer_kind="direct",
            external_message_id=str(message.get("id")) if message.get("id") else None,
            external_user_id=wa_id or None,
            text=text,
            raw_payload=raw_payload,
            display_name=(contact.get("profile") or {}).get("name"),
            username=None,
            metadata={
                "phone_number_id": _metadata(raw_payload).get("phone_number_id"),
                "display_phone_number": _metadata(raw_payload).get(
                    "display_phone_number"
                ),
                "timestamp": message.get("timestamp"),
                "message_type": message.get("type"),
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
        return await self.client.send_text(
            to=external_peer_id,
            text=text,
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
        raise NotImplementedError("WhatsApp Cloud API does not support message edits")

    async def send_typing_indicator(self, *, inbound_message_id: str) -> None:
        await self.client.send_typing_indicator(message_id=inbound_message_id)

    async def validate_credentials(self) -> dict[str, Any]:
        return await self.client.validate()


def _changes(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for entry in raw_payload.get("entry") or []:
        if isinstance(entry, dict):
            changes.extend(
                change
                for change in (entry.get("changes") or [])
                if isinstance(change, dict)
            )
    return changes


def _first_message(raw_payload: dict[str, Any]) -> dict[str, Any] | None:
    for change in _changes(raw_payload):
        value = change.get("value") or {}
        messages = value.get("messages") or []
        if messages and isinstance(messages[0], dict):
            return messages[0]
    if "message" in raw_payload and isinstance(raw_payload["message"], dict):
        return raw_payload["message"]
    return None


def _first_contact(
    raw_payload: dict[str, Any],
    wa_id: object,
) -> dict[str, Any]:
    for change in _changes(raw_payload):
        value = change.get("value") or {}
        for contact in value.get("contacts") or []:
            if isinstance(contact, dict) and (
                wa_id is None or str(contact.get("wa_id")) == str(wa_id)
            ):
                return contact
    return {}


def _metadata(raw_payload: dict[str, Any]) -> dict[str, Any]:
    for change in _changes(raw_payload):
        value = change.get("value") or {}
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    return {}


def _message_text(message: dict[str, Any]) -> str | None:
    message_type = message.get("type")
    if message_type == "text":
        return (message.get("text") or {}).get("body")
    if message_type == "button":
        return (message.get("button") or {}).get("text")
    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        button_reply = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}
        return button_reply.get("title") or list_reply.get("title")
    return None
