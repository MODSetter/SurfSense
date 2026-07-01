"""The seam every ``web.discover`` provider implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.capabilities.web.discover.schemas import DiscoverHit


@runtime_checkable
class DiscoverProvider(Protocol):
    """An env-keyed search backend that suggests candidate URLs for a query."""

    name: str

    def is_available(self) -> bool:
        """True when this provider's platform key/host is configured."""
        ...

    async def search(self, query: str, top_k: int) -> list[DiscoverHit]:
        """Return up to ``top_k`` candidate hits for ``query``."""
        ...
