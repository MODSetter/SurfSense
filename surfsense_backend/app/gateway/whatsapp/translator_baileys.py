"""Translate agent stream events into Baileys bridge messages."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from app.gateway.base.adapter import BasePlatformAdapter, PlatformSendResult
from app.gateway.base.formatting import split_text_message
from app.gateway.base.translator import BaseStreamTranslator, GatewayStreamEvent
from app.gateway.whatsapp.adapter_baileys import WhatsAppBaileysAdapter
from app.observability.metrics import (
    record_gateway_hitl_aborted,
    record_gateway_outbound,
)

logger = logging.getLogger(__name__)

HITL_UNSUPPORTED_MESSAGE = (
    "This action requires approval and is not yet supported from WhatsApp. "
    "Try again with a different request."
)


class WhatsAppBaileysStreamTranslator(BaseStreamTranslator):
    def __init__(
        self,
        *,
        adapter: BasePlatformAdapter,
        external_peer_id: str,
        debounce_seconds: float = 1.5,
    ) -> None:
        self.adapter = adapter
        self.external_peer_id = external_peer_id
        self.debounce_seconds = debounce_seconds
        self._buffer = ""
        self._last_flush_at = 0.0
        self._external_message_ids: list[str] = []

    async def translate(self, events: AsyncIterator[GatewayStreamEvent]) -> None:
        await self._send_typing_indicator()
        async for event in events:
            if event.type in {"text-delta", "text_delta", "text"}:
                self._buffer += str(event.data.get("text") or event.data.get("delta") or "")
                await self._maybe_flush()
            elif event.type in {"data-interrupt-request", "interrupt"}:
                await self._handle_hitl_interrupt()
                return
            elif event.type in {"finish", "done"}:
                break

        await self._flush(final=True)

    async def _maybe_flush(self) -> None:
        now = asyncio.get_running_loop().time()
        if now - self._last_flush_at < self.debounce_seconds:
            return
        await self._flush(final=False)
        self._last_flush_at = now

    async def _flush(self, *, final: bool) -> None:
        if not self._buffer:
            return

        chunks = split_text_message(self._buffer)
        if len(chunks) > 1:
            for chunk in chunks[:-1]:
                result = await self._send_text(chunk)
                self._external_message_ids.append(result.external_message_id)
            self._buffer = chunks[-1]

        if self._external_message_ids:
            await self._edit_text(self._external_message_ids[-1], self._buffer)
        else:
            result = await self._send_text(self._buffer)
            self._external_message_ids.append(result.external_message_id)

        if final:
            logger.debug(
                "WhatsApp Baileys finalized external_ids=%s",
                self._external_message_ids,
            )

    async def _send_typing_indicator(self) -> None:
        if not isinstance(self.adapter, WhatsAppBaileysAdapter):
            return
        try:
            await self.adapter.send_typing_indicator(external_peer_id=self.external_peer_id)
            record_gateway_outbound(platform="whatsapp", kind="typing", status="sent")
        except Exception:
            logger.debug("WhatsApp Baileys typing indicator failed", exc_info=True)

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

    async def _edit_text(self, message_id: str, text: str) -> PlatformSendResult:
        try:
            result = await self.adapter.edit_message(
                external_peer_id=self.external_peer_id,
                external_message_id=message_id,
                text=text,
            )
        except Exception:
            record_gateway_outbound(platform="whatsapp", kind="edit", status="failed")
            raise
        record_gateway_outbound(platform="whatsapp", kind="edit", status="edited")
        return result

    async def _handle_hitl_interrupt(self) -> None:
        if self._buffer:
            await self._flush(final=False)
        await self._send_text(HITL_UNSUPPORTED_MESSAGE)
        record_gateway_hitl_aborted(platform="whatsapp")
