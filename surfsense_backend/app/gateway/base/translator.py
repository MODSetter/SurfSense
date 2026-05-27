"""Base stream translator for platform-specific outbound UX."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GatewayStreamEvent:
    """Small provider-neutral event shape consumed by translators.

    The existing chat stack emits Vercel/assistant-ui events.  Gateway code
    normalizes the subset it needs into this shape before handing it to the
    platform translator.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class BaseStreamTranslator(ABC):
    @abstractmethod
    async def translate(self, events: AsyncIterator[GatewayStreamEvent]) -> None:
        """Consume agent stream events and emit platform messages."""

