"""WhatsApp Cloud API webhook routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import config
from app.db import (
    ExternalChatHealthStatus,
    ExternalChatPlatform,
    get_async_session,
)
from app.gateway.accounts import get_or_create_system_whatsapp_account
from app.gateway.inbox import persist_inbound_event
from app.observability.metrics import (
    record_gateway_inbox_write,
    record_gateway_outbound,
    record_gateway_webhook_parse_error,
)

router = APIRouter(prefix="/gateway/webhooks/whatsapp", tags=["gateway"])
logger = logging.getLogger(__name__)


def _ensure_whatsapp_enabled() -> None:
    if config.GATEWAY_WHATSAPP_INTAKE_MODE == "disabled":
        raise HTTPException(status_code=404, detail="WhatsApp gateway is disabled")


@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> Response:
    _ensure_whatsapp_enabled()
    if (
        hub_mode == "subscribe"
        and config.WHATSAPP_WEBHOOK_VERIFY_TOKEN
        and hmac.compare_digest(hub_verify_token, config.WHATSAPP_WEBHOOK_VERIFY_TOKEN)
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook token")


@router.post("")
async def whatsapp_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    _ensure_whatsapp_enabled()
    raw_body = await request.body()
    _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256"))
    try:
        payload = json.loads(raw_body)
    except ValueError:
        record_gateway_webhook_parse_error()
        return Response(status_code=200)

    try:
        await _process_payload(session, payload)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("WhatsApp webhook processing failed")
        return Response(status_code=200)
    return Response(status_code=200)


def _verify_signature(raw_body: bytes, header_signature: str | None) -> None:
    if not config.WHATSAPP_WEBHOOK_APP_SECRET:
        raise HTTPException(
            status_code=500, detail="WhatsApp app secret is not configured"
        )
    received = (header_signature or "").removeprefix("sha256=")
    expected = hmac.new(
        config.WHATSAPP_WEBHOOK_APP_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(
            status_code=403, detail="Invalid WhatsApp webhook signature"
        )


async def _process_payload(session: AsyncSession, payload: dict[str, Any]) -> None:
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            field = change.get("field")
            value = change.get("value") or {}
            if field == "messages":
                await _process_messages_change(session, payload, entry, change, value)
            elif field == "account_update":
                await _handle_account_update(session, entry, value)
            elif field == "phone_number_quality_update":
                await _handle_phone_number_quality_update(session, entry, value)


async def _process_messages_change(
    session: AsyncSession,
    payload: dict[str, Any],
    entry: dict[str, Any],
    change: dict[str, Any],
    value: dict[str, Any],
) -> None:
    statuses = [
        status for status in value.get("statuses") or [] if isinstance(status, dict)
    ]
    for status in statuses:
        record_gateway_outbound(
            platform="whatsapp",
            kind="status",
            status=str(status.get("status") or "unknown"),
        )

    messages = [msg for msg in value.get("messages") or [] if isinstance(msg, dict)]
    if not messages:
        return

    account = await get_or_create_system_whatsapp_account(session)
    metadata = value.get("metadata") or {}
    if isinstance(metadata, dict):
        cursor_state = dict(account.cursor_state or {})
        for key in ("phone_number_id", "display_phone_number"):
            if metadata.get(key):
                cursor_state[key] = metadata[key]
        account.cursor_state = cursor_state

    for msg in messages:
        message_id = str(msg.get("id") or "")
        if not message_id:
            continue
        request_id = f"gateway_{uuid.uuid4().hex[:16]}"
        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.WHATSAPP,
            event_dedupe_key=f"wamid:{message_id}",
            external_event_id=message_id,
            external_message_id=message_id,
            event_kind="message",
            raw_payload=_single_message_payload(payload, entry, change, msg),
            request_id=request_id,
        )
        record_gateway_inbox_write(platform="whatsapp", dedup_skipped=inbox_id is None)


async def _handle_account_update(
    session: AsyncSession,
    entry: dict[str, Any],
    value: dict[str, Any],
) -> None:
    account = await get_or_create_system_whatsapp_account(session)
    cursor_state = dict(account.cursor_state or {})
    if entry.get("id"):
        cursor_state["waba_id"] = str(entry.get("id"))
    cursor_state["account_update"] = value
    account.cursor_state = cursor_state
    event = str(value.get("event") or value.get("type") or "").upper()
    if event in {"DISABLED_UPDATE", "ACCOUNT_RESTRICTION", "PARTNER_REMOVED"}:
        account.health_status = ExternalChatHealthStatus.FAILING
        account.suspended_at = datetime.now(UTC)
        account.suspended_reason = event.lower()
    elif event in {"VERIFIED_ACCOUNT", "ACCOUNT_ENABLED", "REINSTATED"}:
        account.health_status = ExternalChatHealthStatus.OK
        account.suspended_at = None
        account.suspended_reason = None
    account.last_health_check_at = datetime.now(UTC)


async def _handle_phone_number_quality_update(
    session: AsyncSession,
    entry: dict[str, Any],
    value: dict[str, Any],
) -> None:
    account = await get_or_create_system_whatsapp_account(session)
    cursor_state = dict(account.cursor_state or {})
    if entry.get("id"):
        cursor_state["waba_id"] = str(entry.get("id"))
    cursor_state["quality_update"] = value
    account.cursor_state = cursor_state
    account.last_health_check_at = datetime.now(UTC)


def _single_message_payload(
    payload: dict[str, Any],
    entry: dict[str, Any],
    change: dict[str, Any],
    message: dict[str, Any],
) -> dict[str, Any]:
    value = dict(change.get("value") or {})
    value["messages"] = [message]
    value.pop("statuses", None)
    single_change = {**change, "value": value}
    single_entry = {**entry, "changes": [single_change]}
    return {"object": payload.get("object"), "entry": [single_entry]}
