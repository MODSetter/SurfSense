"""Translate agent stream events into WhatsApp Cloud API messages."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.gateway.base.adapter import BasePlatformAdapter, PlatformSendResult
from app.gateway.base.formatting import split_text_message
from app.gateway.base.translator import BaseStreamTranslator, GatewayStreamEvent
from app.gateway.whatsapp.adapter_cloud import WhatsAppCloudAdapter
from app.observability.metrics import (
    record_gateway_hitl_aborted,
    record_gateway_outbound,
)

logger = logging.getLogger(__name__)

HITL_UNSUPPORTED_MESSAGE = (
    "This action requires approval and is not yet supported from WhatsApp. "
    "Try again with a different request."
)


class WhatsAppCloudStreamTranslator(BaseStreamTranslator):
    def __init__(
        self,
        *,
        adapter: BasePlatformAdapter,
        external_peer_id: str,
        inbound_message_id: str | None = None,
    ) -> None:
        self.adapter = adapter
        self.external_peer_id = external_peer_id
        self.inbound_message_id = inbound_message_id
        self._buffer = ""
        self._typing_sent = False

    async def translate(self, events: AsyncIterator[GatewayStreamEvent]) -> None:
        async for event in events:
            if event.type in {"text-delta", "text_delta", "text"}:
                if not self._typing_sent:
                    await self._send_typing_indicator()
                self._buffer += str(event.data.get("text") or event.data.get("delta") or "")
            elif event.type in {"data-interrupt-request", "interrupt"}:
                await self._handle_hitl_interrupt()
                return
            elif event.type in {"finish", "done"}:
                break

        await self._flush_final()

    async def _flush_final(self) -> None:
        if not self._buffer:
            return
        for chunk in split_text_message(self._buffer):
            await self._send_text(chunk)

    async def _send_typing_indicator(self) -> None:
        self._typing_sent = True
        if not self.inbound_message_id:
            return
        if not isinstance(self.adapter, WhatsAppCloudAdapter):
            return
        try:
            await self.adapter.send_typing_indicator(
                inbound_message_id=self.inbound_message_id
            )
            record_gateway_outbound(platform="whatsapp", kind="typing", status="sent")
        except Exception:
            logger.debug("WhatsApp typing indicator failed", exc_info=True)
            record_gateway_outbound(platform="whatsapp", kind="typing", status="failed")

    async def _send_text(self, text: str) -> PlatformSendResult:
        try:
            result = await self.adapter.send_message(
                external_peer_id=self.external_peer_id,
                text=text,
            )
        except Exception:
            record_gateway_outbound(platform="whatsapp", kind="send", status="failed")
            raise
        record_gateway_outbound(platform="whatsapp", kind="send", status="sent")
        return result

    async def _handle_hitl_interrupt(self) -> None:
        if self._buffer:
            await self._flush_final()
        await self._send_text(HITL_UNSUPPORTED_MESSAGE)
        record_gateway_hitl_aborted(platform="whatsapp")
