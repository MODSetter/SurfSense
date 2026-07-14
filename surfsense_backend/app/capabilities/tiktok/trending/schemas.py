"""``tiktok.trending`` I/O contracts.

The Explore feed (``/api/explore/item_list``) is a single global feed of trending
videos, served to anonymous sessions. No source input is needed — just how many
to return. Each result reuses :class:`TikTokVideoItem`, so trending videos bill on
the same per-video meter as ``tiktok.scrape``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.capabilities.tiktok.scrape.schemas import MAX_TIKTOK_ITEMS
from app.proprietary.platforms.tiktok import TikTokVideoItem


class TrendingInput(BaseModel):
    max_items: int = Field(
        default=20,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max trending videos to return from the Explore feed.",
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable videos for the pre-flight gate (le=100 ceiling)."""
        return self.max_items


class TrendingOutput(BaseModel):
    items: list[TikTokVideoItem] = Field(
        default_factory=list,
        description="One item per trending video returned, in feed order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned video = one billable unit; an ErrorItem (``errorCode`` set,
        for an empty/withheld feed) is surfaced but never charged."""
        return sum(1 for item in self.items if not getattr(item, "errorCode", None))
