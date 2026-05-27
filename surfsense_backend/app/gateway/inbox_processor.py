"""Long-lived gateway inbox processing.

This module owns the agent-turn execution path for messaging gateways.  It is
intentionally independent of Celery so LangGraph, async Postgres, Redis, and
Telegram clients all run on one stable event loop in ``GatewayRunner``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import config
from app.db import (
    GatewayBindingState,
    GatewayConversationBinding,
    GatewayEventStatus,
    GatewayInboundEvent,
    GatewayPeerKind,
    GatewayPlatformAccount,
    NewChatThread,
    async_session_maker,
)
from app.gateway.accounts import account_token
from app.gateway.agent_invoke import call_agent_for_gateway
from app.gateway.bindings import get_or_create_thread_for_binding
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.commands import (
    command_name,
    handle_help_command,
    handle_start_command,
    send_unbound_onboarding,
)
from app.gateway.telegram.translator import TelegramStreamTranslator
from app.observability.metrics import record_gateway_inbox_processed

logger = logging.getLogger(__name__)

SessionMaker = async_sessionmaker[AsyncSession] | Callable[[], AsyncSession]


def _dashboard_url() -> str:
    return config.NEXT_FRONTEND_URL or "/dashboard"


async def claim_next_inbound_event(
    session_maker: SessionMaker = async_session_maker,
) -> int | None:
    """Claim the oldest received inbox event for processing."""

    async with session_maker() as session:
        result = await session.execute(
            select(GatewayInboundEvent)
            .where(GatewayInboundEvent.status == GatewayEventStatus.RECEIVED)
            .order_by(GatewayInboundEvent.received_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        event = result.scalars().first()
        if event is None:
            return None
        event.status = GatewayEventStatus.PROCESSING
        event.attempt_count += 1
        await session.commit()
        return int(event.id)


async def process_inbound_event(
    inbox_id: int,
    session_maker: SessionMaker = async_session_maker,
) -> None:
    """Process one gateway inbox row and mark its terminal status."""

    async with session_maker() as session:
        result = await session.execute(
            select(GatewayInboundEvent)
            .where(GatewayInboundEvent.id == inbox_id)
            .with_for_update(skip_locked=True)
        )
        event = result.scalars().first()
        if event is None or event.status in {
            GatewayEventStatus.PROCESSED,
            GatewayEventStatus.IGNORED,
        }:
            return
        if event.status == GatewayEventStatus.RECEIVED:
            event.status = GatewayEventStatus.PROCESSING
            event.attempt_count += 1
            await session.commit()

    try:
        await _dispatch_inbound_event(inbox_id, session_maker)
    except RuntimeError as exc:
        if str(exc) == "gateway_thread_busy":
            async with session_maker() as session:
                await session.execute(
                    update(GatewayInboundEvent)
                    .where(GatewayInboundEvent.id == inbox_id)
                    .values(
                        status=GatewayEventStatus.RECEIVED,
                        last_error="gateway_thread_busy",
                    )
                )
                await session.commit()
            return
        await _mark_failed(inbox_id, str(exc), session_maker)
        raise
    except Exception as exc:
        await _mark_failed(inbox_id, str(exc), session_maker)
        raise

    async with session_maker() as session:
        event = await session.get(GatewayInboundEvent, inbox_id)
        if event is not None and event.status == GatewayEventStatus.PROCESSING:
            event.status = GatewayEventStatus.PROCESSED
            event.processed_at = datetime.now(UTC)
            await session.commit()
            record_gateway_inbox_processed(platform=event.platform.value, status="processed")


async def _mark_failed(
    inbox_id: int,
    error: str,
    session_maker: SessionMaker,
) -> None:
    async with session_maker() as session:
        await session.execute(
            update(GatewayInboundEvent)
            .where(GatewayInboundEvent.id == inbox_id)
            .values(status=GatewayEventStatus.FAILED, last_error=error)
        )
        await session.commit()


async def _dispatch_inbound_event(
    inbox_id: int,
    session_maker: SessionMaker,
) -> None:
    async with session_maker() as session:
        event = await session.get(GatewayInboundEvent, inbox_id)
        if event is None:
            return
        account = await session.get(GatewayPlatformAccount, event.account_id)
        if account is None:
            event.status = GatewayEventStatus.IGNORED
            event.last_error = "account_missing"
            await session.commit()
            return

        token = account_token(account)
        if not token:
            event.status = GatewayEventStatus.FAILED
            event.last_error = "missing_telegram_token"
            await session.commit()
            return

        adapter = TelegramAdapter(token)
        parsed = adapter.parse_inbound(event.raw_payload or {})
        if parsed.external_peer_id is None:
            event.status = GatewayEventStatus.IGNORED
            event.last_error = "missing_external_peer_id"
            await session.commit()
            return

        _update_account_cursor(account, parsed.metadata.get("update_id"))

        result = await session.execute(
            select(GatewayConversationBinding).where(
                GatewayConversationBinding.account_id == account.id,
                GatewayConversationBinding.external_peer_id == parsed.external_peer_id,
                GatewayConversationBinding.state.in_(
                    [GatewayBindingState.BOUND, GatewayBindingState.SUSPENDED]
                ),
            )
        )
        binding = result.scalars().first()

        if parsed.external_peer_kind != GatewayPeerKind.DIRECT.value:
            await adapter.leave_chat(external_peer_id=parsed.external_peer_id)
            event.status = GatewayEventStatus.IGNORED
            event.last_error = "group_rejected"
            await session.commit()
            return

        cmd = command_name(parsed.text)
        if cmd == "/start":
            handled = await handle_start_command(
                session=session, adapter=adapter, event=parsed
            )
            await session.commit()
            if handled:
                return

        if binding is None:
            await send_unbound_onboarding(
                adapter=adapter,
                event=parsed,
                dashboard_url=_dashboard_url(),
            )
            event.status = GatewayEventStatus.IGNORED
            event.last_error = "unbound_chat"
            await session.commit()
            return

        event.binding_id = binding.id

        if cmd == "/help":
            await handle_help_command(adapter=adapter, event=parsed)
            event.status = GatewayEventStatus.PROCESSED
            await session.commit()
            return
        if cmd == "/new":
            binding.active_thread_id = None
            await adapter.send_message(
                external_peer_id=parsed.external_peer_id,
                text="Started a new SurfSense conversation.",
            )
            event.status = GatewayEventStatus.PROCESSED
            await session.commit()
            return

        if not parsed.text:
            event.status = GatewayEventStatus.IGNORED
            event.last_error = "empty_message"
            await session.commit()
            return

        thread = await get_or_create_thread_for_binding(session, binding)
        await session.commit()

        translator = TelegramStreamTranslator(
            adapter=adapter,
            external_peer_id=parsed.external_peer_id,
        )
        await call_agent_for_gateway(
            session=session,
            binding=binding,
            user_text=parsed.text,
            translator=translator,
            request_id=f"gateway:{inbox_id}",
        )

        thread = await session.get(NewChatThread, thread.id)
        if thread is not None:
            thread.source = "telegram"
        await session.commit()


def _update_account_cursor(account: GatewayPlatformAccount, update_id: object) -> None:
    if update_id is None:
        return
    account.cursor_state = {
        **(account.cursor_state or {}),
        "last_update_id": max(
            int((account.cursor_state or {}).get("last_update_id", 0)),
            int(update_id),
        ),
    }
