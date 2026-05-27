"""Translate agent stream events into Telegram messages."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from telegram.constants import ParseMode

from app.gateway.base.adapter import PlatformSendResult
from app.gateway.base.translator import BaseStreamTranslator, GatewayStreamEvent
from app.gateway.ratelimit import wait_for_token
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.client import retry_plaintext_on_bad_markdown
from app.gateway.telegram.formatting import chunk_message, escape_markdown_v2
from app.observability.metrics import (
    record_gateway_hitl_aborted,
    record_gateway_outbound,
    record_gateway_rate_limit_hit,
)

logger = logging.getLogger(__name__)

HITL_UNSUPPORTED_MESSAGE = (
    "This action requires approval and is not yet supported from Telegram. "
    "Try again with a different request."
)


class TelegramStreamTranslator(BaseStreamTranslator):
    def __init__(
        self,
        *,
        adapter: TelegramAdapter,
        external_peer_id: str,
        assistant_message_id: int | None = None,
        debounce_seconds: float = 1.5,
    ) -> None:
        self.adapter = adapter
        self.external_peer_id = external_peer_id
        self.assistant_message_id = assistant_message_id
        self.debounce_seconds = debounce_seconds
        self._buffer = ""
        self._last_flush_at = 0.0
        self._external_message_ids: list[str] = []
        self._plaintext_mode = False

    async def translate(self, events: AsyncIterator[GatewayStreamEvent]) -> None:
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

        chunks = chunk_message(self._buffer)
        # During streaming, keep edits on the last chunk only.  At final flush,
        # send any additional chunks and mark the message as finalized by the
        # persistence layer (wired through agent/task code).
        if len(chunks) > 1:
            for chunk in chunks[:-1]:
                result = await self._send_text(chunk)
                self._external_message_ids.append(result.external_message_id)
            self._buffer = chunks[-1]

        text = self._format_text(self._buffer)
        if self._external_message_ids:
            await self._edit_text(self._external_message_ids[-1], text)
        else:
            result = await self._send_text(self._buffer)
            self._external_message_ids.append(result.external_message_id)

        if final:
            logger.debug(
                "Telegram gateway finalized assistant message id=%s external_ids=%s",
                self.assistant_message_id,
                self._external_message_ids,
            )

    def _format_text(self, text: str) -> str:
        return text if self._plaintext_mode else escape_markdown_v2(text)

    async def _send_text(self, text: str) -> PlatformSendResult:
        await self._throttle()
        parse_mode = None if self._plaintext_mode else ParseMode.MARKDOWN_V2
        logger.info(
            "Telegram gateway sending message peer=%s chars=%d",
            self.external_peer_id,
            len(text),
        )
        try:
            result = await retry_plaintext_on_bad_markdown(
                self.adapter.send_message,
                external_peer_id=self.external_peer_id,
                text=self._format_text(text),
                parse_mode=parse_mode,
            )
        except Exception:
            record_gateway_outbound(platform="telegram", kind="send", status="failed")
            raise
        logger.info(
            "Telegram gateway sent message peer=%s message_id=%s",
            self.external_peer_id,
            result.external_message_id,
        )
        record_gateway_outbound(platform="telegram", kind="send", status="sent")
        return result

    async def _edit_text(self, message_id: str, text: str) -> PlatformSendResult:
        await self._throttle()
        parse_mode = None if self._plaintext_mode else ParseMode.MARKDOWN_V2
        logger.info(
            "Telegram gateway editing message peer=%s message_id=%s chars=%d",
            self.external_peer_id,
            message_id,
            len(text),
        )
        try:
            result = await retry_plaintext_on_bad_markdown(
                self.adapter.edit_message,
                external_peer_id=self.external_peer_id,
                external_message_id=message_id,
                text=text,
                parse_mode=parse_mode,
            )
        except Exception:
            record_gateway_outbound(platform="telegram", kind="edit", status="failed")
            raise
        logger.info(
            "Telegram gateway edited message peer=%s message_id=%s",
            self.external_peer_id,
            result.external_message_id,
        )
        record_gateway_outbound(platform="telegram", kind="edit", status="edited")
        return result

    async def _throttle(self) -> None:
        chat_wait = await wait_for_token(
            f"tg:chat:{self.external_peer_id}",
            capacity=1,
            refill_per_sec=1.0,
        )
        if chat_wait:
            record_gateway_rate_limit_hit(bucket="tg:chat")
        global_wait = await wait_for_token("tg:global", capacity=25, refill_per_sec=25.0)
        if global_wait:
            record_gateway_rate_limit_hit(bucket="tg:global")

    async def _handle_hitl_interrupt(self) -> None:
        if self._buffer:
            await self._flush(final=False)
        await self._send_text(HITL_UNSUPPORTED_MESSAGE)
        record_gateway_hitl_aborted(platform="telegram")

