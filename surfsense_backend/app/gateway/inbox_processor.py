"""Long-lived external chat inbox processing.

This module owns the agent-turn execution path for external chat surfaces.
FastAPI calls into it after webhook and BYO long-poll intake persist inbox rows.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatEventStatus,
    ExternalChatInboundEvent,
    ExternalChatPeerKind,
    NewChatThread,
    async_session_maker,
)
from app.gateway.agent_invoke import call_agent_for_gateway
from app.gateway.base.commands import command_name
from app.gateway.bindings import get_or_create_thread_for_binding
from app.gateway.registry import resolve_platform_bundle
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
            select(ExternalChatInboundEvent)
            .where(ExternalChatInboundEvent.status == ExternalChatEventStatus.RECEIVED)
            .order_by(ExternalChatInboundEvent.received_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        event = result.scalars().first()
        if event is None:
            return None
        event.status = ExternalChatEventStatus.PROCESSING
        event.attempt_count += 1
        await session.commit()
        return int(event.id)


async def process_inbound_event(
    inbox_id: int,
    session_maker: SessionMaker = async_session_maker,
) -> None:
    """Process one external chat inbox row and mark its terminal status."""

    async with session_maker() as session:
        result = await session.execute(
            select(ExternalChatInboundEvent)
            .where(ExternalChatInboundEvent.id == inbox_id)
            .with_for_update(skip_locked=True)
        )
        event = result.scalars().first()
        if event is None or event.status in {
            ExternalChatEventStatus.PROCESSED,
            ExternalChatEventStatus.IGNORED,
        }:
            return
        if event.status == ExternalChatEventStatus.RECEIVED:
            event.status = ExternalChatEventStatus.PROCESSING
            event.attempt_count += 1
            await session.commit()

    try:
        await _dispatch_inbound_event(inbox_id, session_maker)
    except RuntimeError as exc:
        if str(exc) == "gateway_thread_busy":
            async with session_maker() as session:
                await session.execute(
                    update(ExternalChatInboundEvent)
                    .where(ExternalChatInboundEvent.id == inbox_id)
                    .values(
                        status=ExternalChatEventStatus.RECEIVED,
                        last_error="gateway_thread_busy",
                    )
                )
                await session.commit()
            raise
        await _mark_failed(inbox_id, str(exc), session_maker)
        raise
    except Exception as exc:
        await _mark_failed(inbox_id, str(exc), session_maker)
        raise

    async with session_maker() as session:
        event = await session.get(ExternalChatInboundEvent, inbox_id)
        if event is not None and event.status == ExternalChatEventStatus.PROCESSING:
            event.status = ExternalChatEventStatus.PROCESSED
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
            update(ExternalChatInboundEvent)
            .where(ExternalChatInboundEvent.id == inbox_id)
            .values(status=ExternalChatEventStatus.FAILED, last_error=error)
        )
        await session.commit()


async def _dispatch_inbound_event(
    inbox_id: int,
    session_maker: SessionMaker,
) -> None:
    async with session_maker() as session:
        event = await session.get(ExternalChatInboundEvent, inbox_id)
        if event is None:
            return
        account = await session.get(ExternalChatAccount, event.account_id)
        if account is None:
            event.status = ExternalChatEventStatus.IGNORED
            event.last_error = "account_missing"
            await session.commit()
            return

        try:
            bundle = resolve_platform_bundle(account)
        except RuntimeError as exc:
            event.status = ExternalChatEventStatus.FAILED
            event.last_error = str(exc)
            await session.commit()
            return

        adapter = bundle.adapter
        parsed = adapter.parse_inbound(event.raw_payload or {})
        if parsed.external_peer_id is None:
            event.status = ExternalChatEventStatus.IGNORED
            event.last_error = "missing_external_peer_id"
            await session.commit()
            return

        _update_account_cursor(account, parsed.metadata.get("update_id"))

        result = await session.execute(
            select(ExternalChatBinding).where(
                ExternalChatBinding.account_id == account.id,
                ExternalChatBinding.external_peer_id == parsed.external_peer_id,
                ExternalChatBinding.state.in_(
                    [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
                ),
            )
        )
        binding = result.scalars().first()

        if parsed.external_peer_kind != ExternalChatPeerKind.DIRECT.value:
            if hasattr(adapter, "leave_chat"):
                await adapter.leave_chat(external_peer_id=parsed.external_peer_id)
            event.status = ExternalChatEventStatus.IGNORED
            event.last_error = "group_rejected"
            await session.commit()
            return

        cmd = command_name(parsed.text)
        if cmd == "/start":
            handled = await bundle.commands.handle_start_command(
                session=session, adapter=adapter, event=parsed
            )
            await session.commit()
            if handled:
                return

        if binding is None:
            if bundle.auto_bind_owner and account.owner_user_id and account.owner_search_space_id:
                binding = ExternalChatBinding(
                    account_id=account.id,
                    user_id=account.owner_user_id,
                    search_space_id=account.owner_search_space_id,
                    state=ExternalChatBindingState.BOUND,
                    external_peer_id=parsed.external_peer_id,
                    external_peer_kind=parsed.external_peer_kind,
                    external_display_name=parsed.display_name,
                    external_username=parsed.username,
                    external_metadata=parsed.metadata,
                )
                session.add(binding)
                await session.flush()
            else:
                await bundle.commands.send_unbound_onboarding(
                    adapter=adapter,
                    event=parsed,
                    dashboard_url=_dashboard_url(),
                )
                event.status = ExternalChatEventStatus.IGNORED
                event.last_error = "unbound_chat"
                await session.commit()
                return

        event.external_chat_binding_id = binding.id

        if cmd == "/help":
            handled = await bundle.commands.handle_help_command(adapter=adapter, event=parsed)
            if handled:
                event.status = ExternalChatEventStatus.PROCESSED
                await session.commit()
                return
        if cmd == "/new":
            binding.new_chat_thread_id = None
            await adapter.send_message(
                external_peer_id=parsed.external_peer_id,
                text="Started a new SurfSense conversation.",
            )
            event.status = ExternalChatEventStatus.PROCESSED
            await session.commit()
            return

        if not parsed.text:
            event.status = ExternalChatEventStatus.IGNORED
            event.last_error = "empty_message"
            await session.commit()
            return

        thread = await get_or_create_thread_for_binding(session, binding)
        await session.commit()

        translator = bundle.translator_factory(adapter, parsed)
        await call_agent_for_gateway(
            session=session,
            binding=binding,
            user_text=parsed.text,
            translator=translator,
            platform_label=bundle.platform_label,
            request_id=event.request_id or f"gateway:{inbox_id}",
        )

        thread = await session.get(NewChatThread, thread.id)
        if thread is not None:
            thread.source = bundle.platform_label
        await session.commit()


def _update_account_cursor(account: ExternalChatAccount, update_id: object) -> None:
    if update_id is None:
        return
    account.cursor_state = {
        **(account.cursor_state or {}),
        "last_update_id": max(
            int((account.cursor_state or {}).get("last_update_id", 0)),
            int(update_id),
        ),
    }
