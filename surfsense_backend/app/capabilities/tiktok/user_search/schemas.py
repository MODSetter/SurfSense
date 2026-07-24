"""``tiktok.user_search`` I/O contracts.

Account discovery over ``TikTok``'s Users tab. Where video/general search is
login-walled for anonymous sessions, ``/api/search/user`` returns public account
records, so this verb exposes the one reliably-unblocked search path. Each result
is a :class:`TikTokProfileItem` (the same shape the profile verb emits).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.capabilities.tiktok.scrape.schemas import (
    MAX_TIKTOK_ITEMS,
    MAX_TIKTOK_SOURCES,
)
from app.proprietary.platforms.tiktok import TikTokProfileItem


class UserSearchInput(BaseModel):
    queries: list[str] = Field(
        min_length=1,
        max_length=MAX_TIKTOK_SOURCES,
        description="Keywords to search for TikTok accounts (e.g. names, brands).",
    )
    results_per_query: int = Field(
        default=10,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max accounts to return per query.",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max total accounts to return across all queries.",
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable accounts for the pre-flight gate: ``max_items`` is a
        hard cross-query ceiling (le=100), so no call can exceed it."""
        return self.max_items


class UserSearchOutput(BaseModel):
    items: list[TikTokProfileItem] = Field(
        default_factory=list,
        description="One item per account found, in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned account = one billable unit; ErrorItems (``errorCode`` set,
        for empty/withheld queries) are surfaced but never charged."""
        return sum(1 for item in self.items if not getattr(item, "errorCode", None))
