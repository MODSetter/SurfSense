"""Messaging gateway routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatHealthStatus,
    ExternalChatPeerKind,
    ExternalChatPlatform,
    User,
    get_async_session,
)
from app.gateway.accounts import (
    get_or_create_system_telegram_account,
    get_or_create_system_whatsapp_account,
    get_slack_account_by_team,
)
from app.gateway.bindings import resume_binding, revoke_binding
from app.gateway.inbox import (
    persist_inbound_event,
    slack_event_dedupe_key,
    telegram_event_dedupe_key,
)
from app.gateway.pairing import generate_pairing_code, pairing_expires_at
from app.gateway.slack.adapter import slack_user_peer_id
from app.observability.metrics import (
    record_gateway_inbox_write,
    record_gateway_webhook_parse_error,
)
from app.users import current_active_user
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

router = APIRouter(prefix="/gateway", tags=["gateway"])
logger = logging.getLogger(__name__)

SLACK_AUTHORIZATION_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_BOT_SCOPES = [
    "app_mentions:read",
    "chat:write",
    "channels:read",
    "groups:read",
    "im:write",
    "users:read",
    "team:read",
]
_state_manager: OAuthStateManager | None = None
_token_encryption: TokenEncryption | None = None


def _get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY is not configured")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def _get_token_encryption() -> TokenEncryption:
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY is not configured")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


def _slack_redirect_uri() -> str:
    if config.GATEWAY_SLACK_REDIRECT_URI:
        return config.GATEWAY_SLACK_REDIRECT_URI
    base = config.BACKEND_URL or ""
    return f"{base.rstrip('/')}/api/v1/gateway/slack/callback"


def _slack_frontend_redirect(space_id: int, *, success: bool = False, error: str | None = None) -> RedirectResponse:
    qs = "slack_gateway=connected" if success else f"error={error or 'slack_gateway_failed'}"
    return RedirectResponse(
        url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/user-settings?{qs}"
    )


def verify_slack_signature(*, signing_secret: str, timestamp: str | None, signature: str | None, body: bytes) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 60 * 5:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    digest = hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def _slack_event_kind(payload: dict[str, Any]) -> str:
    event_type = str((payload.get("event") or {}).get("type") or "")
    return "message" if event_type in {"app_mention", "message"} else "other"


class StartBindingRequest(BaseModel):
    platform: ExternalChatPlatform = ExternalChatPlatform.TELEGRAM
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


@router.get("/slack/install")
async def install_slack_gateway(
    search_space_id: int,
    user: User = Depends(current_active_user),
) -> dict[str, str]:
    if not config.GATEWAY_SLACK_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Slack gateway OAuth is not configured")
    state = _get_state_manager().generate_secure_state(search_space_id, user.id)
    auth_params = {
        "client_id": config.GATEWAY_SLACK_CLIENT_ID,
        "scope": ",".join(SLACK_BOT_SCOPES),
        "redirect_uri": _slack_redirect_uri(),
        "state": state,
    }
    return {"auth_url": f"{SLACK_AUTHORIZATION_URL}?{urlencode(auth_params)}"}


@router.get("/slack/callback")
async def slack_gateway_callback(
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    space_id = None
    if state:
        try:
            state_data = _get_state_manager().validate_state(state)
            space_id = int(state_data["space_id"])
        except Exception:
            state_data = None
    else:
        state_data = None

    if error:
        return _slack_frontend_redirect(space_id or 0, error="slack_gateway_oauth_denied")
    if not code or state_data is None:
        raise HTTPException(status_code=400, detail="Invalid Slack gateway OAuth callback")
    if not config.GATEWAY_SLACK_CLIENT_ID or not config.GATEWAY_SLACK_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Slack gateway OAuth is not configured")

    user_id = UUID(state_data["user_id"])
    token_payload = {
        "client_id": config.GATEWAY_SLACK_CLIENT_ID,
        "client_secret": config.GATEWAY_SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": _slack_redirect_uri(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            SLACK_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    token_response.raise_for_status()
    token_json = token_response.json()
    if not token_json.get("ok", False):
        raise HTTPException(
            status_code=400,
            detail=f"Slack gateway OAuth failed: {token_json.get('error', 'unknown_error')}",
        )

    bot_token = token_json.get("access_token")
    team = token_json.get("team") or {}
    team_id = team.get("id")
    if not bot_token or not team_id:
        raise HTTPException(status_code=400, detail="Slack gateway OAuth returned incomplete data")

    bot_user_id = token_json.get("bot_user_id")
    app_id = token_json.get("app_id")
    authed_user = token_json.get("authed_user") or {}
    authed_slack_user_id = authed_user.get("id")
    enc = _get_token_encryption()
    credentials = {
        "bot_token": bot_token,
        "token_type": token_json.get("token_type", "bot"),
        "scope": token_json.get("scope"),
    }
    cursor_state = {
        "team_id": team_id,
        "team_name": team.get("name"),
        "enterprise_id": (token_json.get("enterprise") or {}).get("id"),
        "app_id": app_id,
        "bot_user_id": bot_user_id,
        "scope": token_json.get("scope"),
    }

    account = await get_slack_account_by_team(session, team_id=team_id)
    if account is None:
        account = ExternalChatAccount(
            platform=ExternalChatPlatform.SLACK,
            mode=ExternalChatAccountMode.CLOUD_SHARED,
            is_system_account=True,
            encrypted_credentials=enc.encrypt_token(json.dumps(credentials)),
            bot_username="SurfSense",
            cursor_state=cursor_state,
            health_status=ExternalChatHealthStatus.UNKNOWN,
        )
        session.add(account)
        await session.flush()
    else:
        account.encrypted_credentials = enc.encrypt_token(json.dumps(credentials))
        account.cursor_state = {**(account.cursor_state or {}), **cursor_state}
        account.health_status = ExternalChatHealthStatus.UNKNOWN

    if authed_slack_user_id:
        peer_id = slack_user_peer_id(team_id, authed_slack_user_id)
        existing_binding_result = await session.execute(
            select(ExternalChatBinding).where(
                ExternalChatBinding.account_id == account.id,
                ExternalChatBinding.external_peer_id == peer_id,
                ExternalChatBinding.state.in_(
                    [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
                ),
            )
        )
        binding = existing_binding_result.scalars().first()
        if binding is None:
            session.add(
                ExternalChatBinding(
                    account_id=account.id,
                    user_id=user_id,
                    search_space_id=space_id,
                    state=ExternalChatBindingState.BOUND,
                    external_peer_id=peer_id,
                    external_peer_kind=ExternalChatPeerKind.DIRECT,
                    external_username=authed_slack_user_id,
                    external_metadata={
                        "kind": "slack_user",
                        "team_id": team_id,
                        "slack_user_id": authed_slack_user_id,
                    },
                )
            )
        elif binding.user_id == user_id:
            binding.search_space_id = space_id
            binding.external_metadata = {
                **(binding.external_metadata or {}),
                "kind": "slack_user",
                "team_id": team_id,
                "slack_user_id": authed_slack_user_id,
            }

    await session.commit()
    return _slack_frontend_redirect(space_id, success=True)


@router.post("/webhooks/slack")
async def slack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    body = await request.body()
    if not verify_slack_signature(
        signing_secret=config.GATEWAY_SLACK_SIGNING_SECRET or "",
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
        body=body,
    ):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    try:
        payload = json.loads(body.decode())
    except ValueError:
        record_gateway_webhook_parse_error()
        return Response(status_code=200)

    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge", "")})
    if payload.get("type") != "event_callback":
        return Response(status_code=200)

    event = payload.get("event") or {}
    event_id = payload.get("event_id")
    team_id = payload.get("team_id") or event.get("team")
    if not event_id or not team_id:
        return Response(status_code=200)

    account = await get_slack_account_by_team(session, team_id=str(team_id))
    if account is None:
        logger.warning("Ignoring Slack event for uninstalled team_id=%s", team_id)
        return Response(status_code=200)

    bot_user_id = (account.cursor_state or {}).get("bot_user_id")
    if event.get("bot_id") or (bot_user_id and event.get("user") == bot_user_id):
        return Response(status_code=200)

    try:
        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.SLACK,
            event_dedupe_key=slack_event_dedupe_key(event_id),
            external_event_id=str(event_id),
            external_message_id=str(event.get("ts")) if event.get("ts") else None,
            event_kind=_slack_event_kind(payload),
            raw_payload=payload,
            request_id=f"gateway_{uuid.uuid4().hex[:16]}",
        )
        await session.commit()
        record_gateway_inbox_write(platform="slack", dedup_skipped=inbox_id is None)
    except Exception:
        await session.rollback()
        logger.exception("Slack webhook persistence failed team_id=%s", team_id)
    return Response(status_code=200)


async def _resolve_webhook_account(
    session: AsyncSession,
    *,
    account_id: int,
    header_secret: str | None,
) -> ExternalChatAccount:
    account = await session.get(ExternalChatAccount, account_id)
    if account is None or account.platform != ExternalChatPlatform.TELEGRAM:
        raise HTTPException(status_code=404, detail="Gateway account not found")
    expected_secret = account.webhook_secret or ""
    if not expected_secret or not hmac.compare_digest(header_secret or "", expected_secret):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    return account


@router.post("/webhooks/telegram/{account_id}")
async def telegram_webhook(
    request: Request,
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    request_id = f"gateway_{uuid.uuid4().hex[:16]}"
    try:
        payload = await request.json()
    except ValueError:
        record_gateway_webhook_parse_error()
        return Response(status_code=200)

    account = await _resolve_webhook_account(
        session,
        account_id=account_id,
        header_secret=request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
    )

    try:
        update_id = payload.get("update_id")
        if update_id is None:
            return Response(status_code=200)

        message = _telegram_message(payload) or {}
        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.TELEGRAM,
            event_dedupe_key=telegram_event_dedupe_key(update_id),
            external_event_id=str(update_id),
            external_message_id=(
                str(message["message_id"]) if message.get("message_id") is not None else None
            ),
            event_kind=_classify_telegram_event(payload),
            raw_payload=payload,
            request_id=request_id,
        )
        await session.commit()
        record_gateway_inbox_write(platform="telegram", dedup_skipped=inbox_id is None)
        return Response(status_code=200)
    except Exception:
        await session.rollback()
        logger.exception("Telegram webhook processing failed account_id=%s", account_id)
        return Response(status_code=200)


@router.post("/bindings/start", response_model=StartBindingResponse)
async def start_binding(
    body: StartBindingRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> StartBindingResponse:
    code = generate_pairing_code()
    if body.platform == ExternalChatPlatform.TELEGRAM:
        account = await get_or_create_system_telegram_account(session)
        username = account.bot_username or config.TELEGRAM_SHARED_BOT_USERNAME
        if not username:
            raise HTTPException(
                status_code=500,
                detail="Telegram bot username is not configured",
            )
        deep_link = f"https://t.me/{username}?start={code}"
    elif body.platform == ExternalChatPlatform.WHATSAPP:
        if config.GATEWAY_WHATSAPP_INTAKE_MODE != "cloud":
            raise HTTPException(
                status_code=400,
                detail="WhatsApp /start pairing requires GATEWAY_WHATSAPP_INTAKE_MODE=cloud",
            )
        account = await get_or_create_system_whatsapp_account(session)
        phone = config.WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER
        if not phone:
            raise HTTPException(
                status_code=500,
                detail="WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER is not configured",
            )
        normalized_phone = "".join(ch for ch in phone if ch.isdigit())
        if not normalized_phone:
            raise HTTPException(
                status_code=500,
                detail="WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER must contain digits",
            )
        deep_link = f"https://wa.me/{normalized_phone}?text={quote(f'/start {code}')}"
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    expires_at = pairing_expires_at()
    binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user.id,
        search_space_id=body.search_space_id,
        state=ExternalChatBindingState.PENDING,
        pairing_code=code,
        pairing_code_expires_at=expires_at,
    )
    session.add(binding)
    await session.commit()
    await session.refresh(binding)

    return StartBindingResponse(
        binding_id=binding.id,
        code=code,
        deep_link=deep_link,
        expires_at=expires_at,
    )


@router.get("/bindings")
async def list_bindings(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(ExternalChatBinding, ExternalChatAccount)
        .join(ExternalChatAccount, ExternalChatBinding.account_id == ExternalChatAccount.id)
        .where(ExternalChatBinding.user_id == user.id)
    )
    return [
        {
            "id": binding.id,
            "platform": account.platform.value,
            "state": binding.state.value,
            "search_space_id": binding.search_space_id,
            "external_display_name": binding.external_display_name,
            "external_username": binding.external_username,
            "external_metadata": binding.external_metadata,
            "suspended_reason": binding.suspended_reason,
        }
        for binding, account in result.all()
    ]


@router.get("/platforms")
async def list_platforms(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(ExternalChatAccount).where(
            (ExternalChatAccount.owner_user_id == user.id)
            | (ExternalChatAccount.is_system_account.is_(True))
        )
    )
    return [
        {
            "id": account.id,
            "platform": account.platform.value,
            "mode": account.mode.value,
            "bot_username": account.bot_username,
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
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    revoke_binding(binding)
    await session.commit()
    return {"ok": True}


@router.post("/bindings/{binding_id}/resume")
async def resume_external_chat_binding(
    binding_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, bool]:
    binding = await session.get(ExternalChatBinding, binding_id)
    if binding is None or binding.user_id != user.id:
        raise HTTPException(status_code=404, detail="Binding not found")
    resume_binding(binding)
    binding.updated_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}

