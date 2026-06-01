"""Provider-neutral command hooks for external chat gateways."""

from __future__ import annotations

from app.gateway.base.adapter import BasePlatformAdapter, ParsedInboundEvent


def command_name(text: str | None) -> str | None:
    if not text or not text.startswith("/"):
        return None
    return text.split(maxsplit=1)[0].split("@", 1)[0].lower()


class BaseGatewayCommands:
    """Default command behavior for platforms without slash-command onboarding."""

    async def handle_start_command(
        self,
        *,
        session,
        adapter: BasePlatformAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return False

    async def handle_help_command(
        self,
        *,
        adapter: BasePlatformAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return False

    async def send_unbound_onboarding(
        self,
        *,
        adapter: BasePlatformAdapter,
        event: ParsedInboundEvent,
        dashboard_url: str,
    ) -> None:
        return None
