"""Invoke SurfSense chat agent for external chat surfaces."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ExternalChatBinding, NewChatMessage
from app.gateway.auth_invariant import assert_authorization_invariant
from app.gateway.base.translator import BaseStreamTranslator, GatewayStreamEvent
from app.gateway.bindings import get_or_create_thread_for_binding
from app.gateway.hitl_filter import DEFAULT_HITL_TOOL_NAMES
from app.gateway.thread_lock import acquire_thread_lock, release_thread_lock
from app.observability.metrics import record_gateway_turn_latency
from app.tasks.chat.stream_new_chat import stream_new_chat

logger = logging.getLogger(__name__)


async def _events_from_sse(chunks: AsyncIterator[str]) -> AsyncIterator[GatewayStreamEvent]:
    saw_text = False
    async for chunk in chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            payload = line.removeprefix("data:").strip()
            if payload == "[DONE]":
                logger.info("Gateway SSE normalized: done")
                yield GatewayStreamEvent(type="done")
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            event_type = str(data.get("type") or "")
            if event_type == "text-delta":
                delta = data.get("delta", "")
                if delta and not saw_text:
                    logger.info("Gateway SSE normalized: text stream started")
                    saw_text = True
                yield GatewayStreamEvent(type="text-delta", data={"delta": delta})
            elif event_type in {"finish", "done"}:
                logger.info("Gateway SSE normalized: %s", event_type)
                yield GatewayStreamEvent(type="finish", data=data)
            elif event_type == "data-interrupt-request":
                logger.info("Gateway SSE normalized: interrupt request")
                yield GatewayStreamEvent(type="data-interrupt-request", data=data)


async def call_agent_for_gateway(
    *,
    session: AsyncSession,
    binding: ExternalChatBinding,
    user_text: str,
    translator: BaseStreamTranslator,
    platform_label: str = "telegram",
    request_id: str | None = None,
) -> None:
    user = await assert_authorization_invariant(session, binding)
    thread = await get_or_create_thread_for_binding(session, binding)
    await session.commit()

    if not acquire_thread_lock(thread.id):
        raise RuntimeError("gateway_thread_busy")

    try:
        stream = stream_new_chat(
            user_query=user_text,
            search_space_id=binding.search_space_id,
            chat_id=thread.id,
            user_id=str(user.id),
            needs_history_bootstrap=thread.needs_history_bootstrap,
            thread_visibility=thread.visibility,
            current_user_display_name=user.display_name or "A team member",
            disabled_tools=sorted(DEFAULT_HITL_TOOL_NAMES),
            request_id=request_id or "gateway",
        )
        events = _events_from_sse(stream)
        try:
            await translator.translate(events)
        finally:
            await events.aclose()
            await stream.aclose()
        await session.execute(
            update(NewChatMessage)
            .where(
                NewChatMessage.thread_id == thread.id,
                NewChatMessage.source == "surfsense",
            )
            .values(source=platform_label)
        )
        await session.commit()
        record_gateway_turn_latency(0, platform=platform_label)
    finally:
        release_thread_lock(thread.id)

