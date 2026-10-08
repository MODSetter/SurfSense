"""Search answers for queries already asked, for one window.

Hugging Face allows 500 requests per 5 minutes; a burst of typing must not
spend them. In memory and forgetful: a cached answer is a convenience, never
a record. Shaped like the install TicketStore, keyed on query and limit.
"""

import time
from dataclasses import dataclass

from modules.llm.catalog.local.engines.llamacpp.search.hits import SearchHit

# The same window the renderer's search cache uses.
TTL_SECONDS = 300.0


@dataclass(frozen=True)
class _Entry:
    hits: list[SearchHit]
    stored_at: float


class SearchCache:
    def __init__(self, *, ttl_seconds: float = TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[tuple[str, int], _Entry] = {}

    def get(
        self, query: str, limit: int, *, now: float | None = None
    ) -> list[SearchHit] | None:
        self._expire(now)
        entry = self._entries.get((query, limit))
        return entry.hits if entry is not None else None

    def put(
        self,
        query: str,
        limit: int,
        hits: list[SearchHit],
        *,
        now: float | None = None,
    ) -> None:
        self._expire(now)
        self._entries[(query, limit)] = _Entry(
            hits, now if now is not None else time.monotonic()
        )

    def _expire(self, now: float | None) -> None:
        cutoff = (now if now is not None else time.monotonic()) - self._ttl
        for key, entry in list(self._entries.items()):
            if entry.stored_at < cutoff:
                del self._entries[key]
