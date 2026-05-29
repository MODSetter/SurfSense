"""Resolve gateway platform implementations from account rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.db import ExternalChatAccount, ExternalChatAccountMode, ExternalChatPlatform
from app.gateway.accounts import account_token
from app.gateway.base.adapter import BasePlatformAdapter, ParsedInboundEvent
from app.gateway.base.commands import BaseGatewayCommands
from app.gateway.base.translator import BaseStreamTranslator
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.commands import TelegramGatewayCommands
from app.gateway.telegram.translator import TelegramStreamTranslator

TranslatorFactory = Callable[
    [BasePlatformAdapter, ParsedInboundEvent],
    BaseStreamTranslator,
]


@dataclass(frozen=True)
class PlatformBundle:
    adapter: BasePlatformAdapter
    translator_factory: TranslatorFactory
    platform_label: str
    commands: BaseGatewayCommands
    auto_bind_owner: bool = False


def _telegram_translator_factory(
    adapter: BasePlatformAdapter,
    event: ParsedInboundEvent,
) -> BaseStreamTranslator:
    if event.external_peer_id is None:
        raise RuntimeError("missing_external_peer_id")
    return TelegramStreamTranslator(
        adapter=adapter,  # type: ignore[arg-type]
        external_peer_id=event.external_peer_id,
    )


def _whatsapp_cloud_translator_factory(
    adapter: BasePlatformAdapter,
    event: ParsedInboundEvent,
) -> BaseStreamTranslator:
    if event.external_peer_id is None:
        raise RuntimeError("missing_external_peer_id")
    from app.gateway.whatsapp.translator import WhatsAppCloudStreamTranslator

    return WhatsAppCloudStreamTranslator(
        adapter=adapter,
        external_peer_id=event.external_peer_id,
        inbound_message_id=event.external_message_id,
    )


def _whatsapp_baileys_translator_factory(
    adapter: BasePlatformAdapter,
    event: ParsedInboundEvent,
) -> BaseStreamTranslator:
    if event.external_peer_id is None:
        raise RuntimeError("missing_external_peer_id")
    from app.gateway.whatsapp.translator_baileys import WhatsAppBaileysStreamTranslator

    return WhatsAppBaileysStreamTranslator(
        adapter=adapter,
        external_peer_id=event.external_peer_id,
    )


def resolve_platform_bundle(account: ExternalChatAccount) -> PlatformBundle:
    if account.platform == ExternalChatPlatform.TELEGRAM:
        token = account_token(account)
        if not token:
            raise RuntimeError("missing_telegram_token")
        return PlatformBundle(
            adapter=TelegramAdapter(token),
            translator_factory=_telegram_translator_factory,
            platform_label="telegram",
            commands=TelegramGatewayCommands(),
        )

    if account.platform == ExternalChatPlatform.WHATSAPP:
        if account.mode == ExternalChatAccountMode.CLOUD_SHARED:
            from app.gateway.whatsapp.adapter_cloud import WhatsAppCloudAdapter
            from app.gateway.whatsapp.commands import WhatsAppGatewayCommands
            from app.gateway.whatsapp.credentials import (
                load_system_whatsapp_credentials,
            )

            return PlatformBundle(
                adapter=WhatsAppCloudAdapter(load_system_whatsapp_credentials()),
                translator_factory=_whatsapp_cloud_translator_factory,
                platform_label="whatsapp",
                commands=WhatsAppGatewayCommands(),
                auto_bind_owner=False,
            )
        if account.mode == ExternalChatAccountMode.SELF_HOST_BYO:
            from app.gateway.whatsapp.adapter_baileys import WhatsAppBaileysAdapter

            return PlatformBundle(
                adapter=WhatsAppBaileysAdapter(),
                translator_factory=_whatsapp_baileys_translator_factory,
                platform_label="whatsapp",
                commands=BaseGatewayCommands(),
                auto_bind_owner=True,
            )

    raise RuntimeError(f"unsupported_gateway_platform:{account.platform.value}:{account.mode.value}")
