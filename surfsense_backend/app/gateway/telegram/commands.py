"""Telegram command handlers."""

from __future__ import annotations

from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.base.commands import BaseGatewayCommands
from app.gateway.pairing import redeem_pairing_code
from app.gateway.ratelimit import acquire_token
from app.gateway.telegram.adapter import TelegramAdapter

HELP_TEXT = (
    "SurfSense Telegram commands:\n"
    "/start <code> - pair this chat\n"
    "/new - start a fresh conversation\n"
    "/help - show this help"
)


async def handle_start_command(
    *,
    session,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
) -> bool:
    text = event.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not event.external_peer_id:
        await adapter.send_message(
            external_peer_id=event.external_peer_id or "",
            text="Generate a pairing code in SurfSense Settings > Messaging Channels, then send /start CODE here.",
        )
        return True

    binding = await redeem_pairing_code(
        session,
        code=parts[1].strip(),
        external_peer_id=event.external_peer_id,
        external_peer_kind=event.external_peer_kind,
        external_display_name=event.display_name,
        external_username=event.username,
        external_metadata=event.metadata,
    )
    if binding is None:
        await adapter.send_message(
            external_peer_id=event.external_peer_id,
            text="That pairing code is invalid or expired. Generate a new code in SurfSense.",
        )
        return True

    await adapter.send_message(
        external_peer_id=event.external_peer_id,
        text="SurfSense is connected. Send a message here to chat with your agent.",
    )
    return True


async def handle_help_command(*, adapter: TelegramAdapter, event: ParsedInboundEvent) -> bool:
    if not event.external_peer_id:
        return True
    await adapter.send_message(external_peer_id=event.external_peer_id, text=HELP_TEXT)
    return True


async def send_unbound_onboarding(
    *,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    dashboard_url: str,
) -> None:
    if not event.external_peer_id:
        return
    wait_ms = await acquire_token(
        f"tg:onboarded:{event.external_peer_id}",
        capacity=1,
        refill_per_sec=1 / 3600,
    )
    if wait_ms > 0:
        return
    await adapter.send_message(
        external_peer_id=event.external_peer_id,
        text=(
            "Hi! To use SurfSense via Telegram, generate a pairing code at "
            f"{dashboard_url} and send /start CODE here."
        ),
    )


class TelegramGatewayCommands(BaseGatewayCommands):
    async def handle_start_command(
        self,
        *,
        session,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return await handle_start_command(session=session, adapter=adapter, event=event)

    async def handle_help_command(
        self,
        *,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return await handle_help_command(adapter=adapter, event=event)

    async def send_unbound_onboarding(
        self,
        *,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        dashboard_url: str,
    ) -> None:
        await send_unbound_onboarding(
            adapter=adapter,
            event=event,
            dashboard_url=dashboard_url,
        )