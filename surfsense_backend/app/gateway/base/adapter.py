"""Platform adapter interfaces for messaging gateways."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedInboundEvent:
    platform: str
    event_kind: str
    external_peer_id: str | None
    external_peer_kind: str
    external_message_id: str | None
    external_user_id: str | None
    text: str | None
    raw_payload: dict[str, Any]
    display_name: str | None = None
    username: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformSendResult:
    external_message_id: str
    raw_response: dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(ABC):
    platform: str

    @abstractmethod
    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        """Parse a provider webhook/update into the gateway's normalized shape."""

    @abstractmethod
    async def send_message(
        self,
        *,
        external_peer_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> PlatformSendResult:
        """Send a new platform message."""

    @abstractmethod
    async def edit_message(
        self,
        *,
        external_peer_id: str,
        external_message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> PlatformSendResult:
        """Edit an existing platform message."""

    @abstractmethod
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate configured credentials and return account metadata."""

    async def fetch_updates(
        self, *, offset: int | None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield provider updates for long-polling adapters."""
        if False:
            yield {}  # pragma: no cover
        raise NotImplementedError("This adapter does not support long-polling")
