"""Translate agent stream events into Slack thread replies."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.gateway.base.adapter import PlatformSendResult
from app.gateway.base.formatting import split_text_message
from app.gateway.base.translator import BaseStreamTranslator, GatewayStreamEvent
from app.gateway.ratelimit import wait_for_token
from app.gateway.slack.adapter import SlackAdapter
from app.observability.metrics import (
    record_gateway_hitl_aborted,
    record_gateway_outbound,
    record_gateway_rate_limit_hit,
)

logger = logging.getLogger(__name__)

SLACK_MAX_MESSAGE_CHARS = 35000
HITL_UNSUPPORTED_MESSAGE = (
    "This action requires approval and is not yet supported from Slack. "
    "Try again with a different request."
)


class SlackStreamTranslator(BaseStreamTranslator):
    def __init__(
        self,
        *,
        adapter: SlackAdapter,
        channel_id: str,
        thread_ts: str,
    ) -> None:
        self.adapter = adapter
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self._buffer = ""

    async def translate(self, events: AsyncIterator[GatewayStreamEvent]) -> None:
        async for event in events:
            if event.type in {"text-delta", "text_delta", "text"}:
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
        for chunk in split_text_message(self._buffer, max_chars=SLACK_MAX_MESSAGE_CHARS):
            await self._send_text(chunk)

    async def _send_text(self, text: str) -> PlatformSendResult:
        await self._throttle()
        try:
            result = await self.adapter.send_message(
                external_peer_id=self.channel_id,
                text=text,
                reply_to_message_id=self.thread_ts,
            )
        except Exception:
            record_gateway_outbound(platform="slack", kind="send", status="failed")
            raise
        record_gateway_outbound(platform="slack", kind="send", status="sent")
        return result

    async def _throttle(self) -> None:
        chat_wait = await wait_for_token(
            f"slack:channel:{self.channel_id}",
            capacity=1,
            refill_per_sec=1.0,
        )
        if chat_wait:
            record_gateway_rate_limit_hit(bucket="slack:channel")

    async def _handle_hitl_interrupt(self) -> None:
        if self._buffer:
            await self._flush_final()
        await self._send_text(HITL_UNSUPPORTED_MESSAGE)
        record_gateway_hitl_aborted(platform="slack")
