"""Messaging gateway routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import config
from app.db import (
    GatewayBindingState,
    GatewayConversationBinding,
    GatewayPlatform,
    GatewayPlatformAccount,
    User,
    get_async_session,
)
from app.gateway.accounts import get_or_create_system_telegram_account
from app.gateway.bindings import resume_binding, revoke_binding
from app.gateway.inbox import persist_inbound_event, telegram_event_dedupe_key
from app.gateway.pairing import generate_pairing_code, pairing_expires_at
from app.observability.metrics import record_gateway_inbox_write
from app.rate_limiter import limiter
from app.users import current_active_user

router = APIRouter(prefix="/gateway", tags=["gateway"])


class StartBindingRequest(BaseModel):
    platform: GatewayPlatform = GatewayPlatform.TELEGRAM
    search_space_id: int


class StartBindingResponse(BaseModel):
    binding_id: int
    code: str
    deep_link: str
    expires_at: datetime


def _classify_telegram_event(payload: dict[str, Any]) -> str:
    if "message" in payload:
        return "message"
    if "edited_message" in payload:
        return "edited_message"
    if "callback_query" in payload:
        return "callback_query"
    return "other"


def _telegram_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    return payload.get("message") or payload.get("edited_message")


async def _resolve_webhook_account(
    session: AsyncSession,
    *,
    secret: str,
    header_secret: str | None,
) -> GatewayPlatformAccount:
    if config.TELEGRAM_WEBHOOK_SECRET and secret == config.TELEGRAM_WEBHOOK_SECRET:
        if header_secret != config.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
        return await get_or_create_system_telegram_account(session)

    result = await session.execute(
        select(GatewayPlatformAccount).where(
            GatewayPlatformAccount.platform == GatewayPlatform.TELEGRAM
        )
    )
    for account in result.scalars():
        metadata = account.account_metadata or {}
        webhook_secret = metadata.get("webhook_secret")
        if webhook_secret and webhook_secret == secret:
            if header_secret != webhook_secret:
                raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
            return account

    raise HTTPException(status_code=404, detail="Gateway account not found")


@router.post("/webhooks/telegram/{secret}")
@limiter.limit("60/minute", key_func=lambda request: f"tg-webhook:{request.path_params['secret']}")
async def telegram_webhook(
    request: Request,
    secret: str,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    payload = await request.json()
    account = await _resolve_webhook_account(
        session,
        secret=secret,
        header_secret=request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
    )
    update_id = payload.get("update_id")
    if update_id is None:
        return Response(status_code=200)

    message = _telegram_message(payload) or {}
    inbox_id = await persist_inbound_event(
        session,
        account_id=account.id,
        platform=GatewayPlatform.TELEGRAM,
        event_dedupe_key=telegram_event_dedupe_key(update_id),
        external_event_id=str(update_id),
        external_message_id=(
            str(message["message_id"]) if message.get("message_id") is not None else None
        ),
        event_kind=_classify_telegram_event(payload),
        raw_payload=payload,
    )
    await session.commit()
    record_gateway_inbox_write(platform="telegram", dedup_skipped=inbox_id is None)
    return Response(status_code=200)


@router.post("/bindings/start", response_model=StartBindingResponse)
async def start_binding(
    body: StartBindingRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> StartBindingResponse:
    if body.platform != GatewayPlatform.TELEGRAM:
        raise HTTPException(status_code=400, detail="Only Telegram is supported in v1")

    account = await get_or_create_system_telegram_account(session)
    code = generate_pairing_code()
    expires_at = pairing_expires_at()
    binding = GatewayConversationBinding(
        account_id=account.id,
        user_id=user.id,
        search_space_id=body.search_space_id,
        state=GatewayBindingState.PENDING,
        pairing_code=code,
        pairing_code_expires_at=expires_at,
    )
    session.add(binding)
    await session.commit()
    await session.refresh(binding)

    username = account.account_metadata.get("bot_username") or config.TELEGRAM_SHARED_BOT_USERNAME
    if not username:
        raise HTTPException(status_code=500, detail="Telegram bot username is not configured")
    return StartBindingResponse(
        binding_id=binding.id,
        code=code,
        deep_link=f"https://t.me/{username}?start={code}",
        expires_at=expires_at,
    )


@router.get("/bindings")
async def list_bindings(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(GatewayConversationBinding).where(
            GatewayConversationBinding.user_id == user.id
        )
    )
    return [
        {
            "id": binding.id,
            "platform": "telegram",
            "state": binding.state.value,
            "search_space_id": binding.search_space_id,
            "external_display_name": binding.external_display_name,
            "external_username": binding.external_username,
            "suspended_reason": binding.suspended_reason,
        }
        for binding in result.scalars()
    ]


@router.get("/platforms")
async def list_platforms(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(GatewayPlatformAccount).where(
            (GatewayPlatformAccount.owner_user_id == user.id)
            | (GatewayPlatformAccount.is_system_account.is_(True))
        )
    )
    return [
        {
            "id": account.id,
            "platform": account.platform.value,
            "mode": account.mode.value,
            "bot_username": (account.account_metadata or {}).get("bot_username"),
            "health_status": account.health_status.value,
            "last_health_check_at": account.last_health_check_at,
        }
        for account in result.scalars()
    ]


@router.delete("/bindings/{binding_id}")
async def delete_binding(
    binding_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    binding = await session.get(GatewayConversationBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    revoke_binding(binding)
    await session.commit()
    return {"ok": True}


@router.post("/bindings/{binding_id}/resume")
async def resume_gateway_binding(
    binding_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    binding = await session.get(GatewayConversationBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    resume_binding(binding)
    binding.updated_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}

