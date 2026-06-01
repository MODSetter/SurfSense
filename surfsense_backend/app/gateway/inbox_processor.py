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
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatEventStatus,
    ExternalChatInboundEvent,
    ExternalChatPeerKind,
    ExternalChatPlatform,
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


def _active_whatsapp_account_mode() -> ExternalChatAccountMode | None:
    if config.GATEWAY_WHATSAPP_INTAKE_MODE == "cloud":
        return ExternalChatAccountMode.CLOUD_SHARED
    if config.GATEWAY_WHATSAPP_INTAKE_MODE == "baileys":
        return ExternalChatAccountMode.SELF_HOST_BYO
    return None


def _is_inactive_whatsapp_account(account: ExternalChatAccount) -> bool:
    return (
        account.platform == ExternalChatPlatform.WHATSAPP
        and account.mode != _active_whatsapp_account_mode()
    )


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


async def _resolve_binding_for_event(
    session: AsyncSession,
    account: ExternalChatAccount,
    parsed,
) -> ExternalChatBinding | None:
    if account.platform == ExternalChatPlatform.SLACK:
        return await _resolve_slack_thread_binding(session, account, parsed)
    if account.platform == ExternalChatPlatform.DISCORD:
        return await _resolve_discord_thread_binding(session, account, parsed)

    result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.external_peer_id == parsed.external_peer_id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    return result.scalars().first()


async def _resolve_slack_thread_binding(
    session: AsyncSession,
    account: ExternalChatAccount,
    parsed,
) -> ExternalChatBinding | None:
    user_peer_id = parsed.metadata.get("slack_user_peer_id")
    thread_peer_id = parsed.metadata.get("slack_thread_peer_id") or parsed.external_peer_id
    if not user_peer_id or not thread_peer_id:
        return None

    user_result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.external_peer_id == user_peer_id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    user_binding = user_result.scalars().first()
    if user_binding is None:
        return None

    thread_result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.external_peer_id == thread_peer_id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    thread_binding = thread_result.scalars().first()
    if thread_binding is not None:
        return thread_binding

    thread_binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user_binding.user_id,
        search_space_id=user_binding.search_space_id,
        state=ExternalChatBindingState.BOUND,
        external_peer_id=thread_peer_id,
        external_peer_kind=ExternalChatPeerKind.CHANNEL,
        external_thread_id=parsed.metadata.get("thread_ts"),
        external_display_name=parsed.metadata.get("channel_id"),
        external_username=parsed.external_user_id,
        external_metadata={
            "kind": "slack_thread",
            "team_id": parsed.metadata.get("team_id"),
            "channel_id": parsed.metadata.get("channel_id"),
            "thread_ts": parsed.metadata.get("thread_ts"),
            "slack_user_id": parsed.metadata.get("slack_user_id"),
            "user_binding_id": user_binding.id,
        },
    )
    session.add(thread_binding)
    await session.flush()
    return thread_binding


async def _resolve_discord_thread_binding(
    session: AsyncSession,
    account: ExternalChatAccount,
    parsed,
) -> ExternalChatBinding | None:
    user_peer_id = parsed.metadata.get("discord_user_peer_id")
    thread_peer_id = parsed.metadata.get("discord_thread_peer_id") or parsed.external_peer_id
    if not user_peer_id or not thread_peer_id:
        return None

    user_result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.external_peer_id == user_peer_id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    user_binding = user_result.scalars().first()
    if user_binding is None:
        return None

    thread_result = await session.execute(
        select(ExternalChatBinding).where(
            ExternalChatBinding.account_id == account.id,
            ExternalChatBinding.external_peer_id == thread_peer_id,
            ExternalChatBinding.state.in_(
                [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
            ),
        )
    )
    thread_binding = thread_result.scalars().first()
    if thread_binding is not None:
        return thread_binding

    thread_binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user_binding.user_id,
        search_space_id=user_binding.search_space_id,
        state=ExternalChatBindingState.BOUND,
        external_peer_id=thread_peer_id,
        external_peer_kind=ExternalChatPeerKind.CHANNEL,
        external_thread_id=parsed.metadata.get("thread_key"),
        external_display_name=parsed.metadata.get("channel_id"),
        external_username=parsed.external_user_id,
        external_metadata={
            "kind": "discord_thread",
            "guild_id": parsed.metadata.get("guild_id"),
            "channel_id": parsed.metadata.get("channel_id"),
            "thread_key": parsed.metadata.get("thread_key"),
            "discord_user_id": parsed.metadata.get("discord_user_id"),
            "user_binding_id": user_binding.id,
        },
    )
    session.add(thread_binding)
    await session.flush()
    return thread_binding


def _reply_target(parsed) -> tuple[str | None, str | None]:
    if parsed.platform == "slack":
        return parsed.metadata.get("channel_id"), parsed.metadata.get("thread_ts")
    if parsed.platform == "discord":
        return parsed.metadata.get("channel_id"), parsed.metadata.get("message_id")
    return parsed.external_peer_id, None


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
        if _is_inactive_whatsapp_account(account):
            event.status = ExternalChatEventStatus.IGNORED
            event.last_error = "inactive_whatsapp_mode"
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

        binding = await _resolve_binding_for_event(session, account, parsed)

        if (
            account.platform
            not in {ExternalChatPlatform.SLACK, ExternalChatPlatform.DISCORD}
            and parsed.external_peer_kind != ExternalChatPeerKind.DIRECT.value
        ):
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
            reply_peer_id, reply_message_id = _reply_target(parsed)
            if reply_peer_id:
                await adapter.send_message(
                    external_peer_id=reply_peer_id,
                    text="Started a new SurfSense conversation.",
                    reply_to_message_id=reply_message_id,
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
