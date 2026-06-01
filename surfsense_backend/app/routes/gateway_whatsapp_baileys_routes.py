"""Routes for the self-hosted WhatsApp Baileys bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
    User,
    get_async_session,
)
from app.gateway.whatsapp.adapter_baileys import WhatsAppBaileysAdapter
from app.users import current_active_user
from app.utils.rbac import check_search_space_access

router = APIRouter(prefix="/gateway/whatsapp/baileys", tags=["gateway"])


class BaileysPairRequest(BaseModel):
    search_space_id: int
    phone_number: str


def _ensure_baileys_enabled() -> None:
    if config.GATEWAY_WHATSAPP_INTAKE_MODE != "baileys":
        raise HTTPException(status_code=404, detail="WhatsApp Baileys gateway is disabled")
    if config.is_cloud():
        raise HTTPException(
            status_code=403,
            detail="Baileys is only available for self-hosted SurfSense installs",
        )


async def _get_user_whatsapp_account(
    session: AsyncSession,
    user: User,
) -> ExternalChatAccount | None:
    result = await session.execute(
        select(ExternalChatAccount).where(
            ExternalChatAccount.owner_user_id == user.id,
            ExternalChatAccount.platform == ExternalChatPlatform.WHATSAPP,
            ExternalChatAccount.is_system_account.is_(False),
        )
    )
    return result.scalars().first()


@router.post("/pair")
async def request_pairing_code(
    body: BaileysPairRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    _ensure_baileys_enabled()
    await check_search_space_access(session, user, body.search_space_id)
    adapter = WhatsAppBaileysAdapter()
    try:
        pairing = await adapter.request_pairing_code(phone_number=body.phone_number)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    account = await _get_user_whatsapp_account(session, user)
    if account is None:
        account = ExternalChatAccount(
            platform=ExternalChatPlatform.WHATSAPP,
            mode=ExternalChatAccountMode.SELF_HOST_BYO,
            owner_user_id=user.id,
            owner_search_space_id=body.search_space_id,
            is_system_account=False,
            cursor_state={},
            health_status=ExternalChatHealthStatus.UNKNOWN,
        )
        session.add(account)
    else:
        account.mode = ExternalChatAccountMode.SELF_HOST_BYO
        account.owner_search_space_id = body.search_space_id
        account.health_status = ExternalChatHealthStatus.UNKNOWN
        account.suspended_at = None
        account.suspended_reason = None
    account.last_health_check_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(account)
    return {"account_id": account.id, **pairing}


@router.get("/health")
async def bridge_health(
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    _ensure_baileys_enabled()
    adapter = WhatsAppBaileysAdapter()
    try:
        return await adapter.validate_credentials()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
