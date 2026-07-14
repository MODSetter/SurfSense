"""``tiktok.comments`` I/O contracts.

URL-only: given TikTok video URLs, return each video's public comment thread.
Unlike profile-video/general-search feeds, ``/api/comment/list`` is served to
anonymous sessions once the comments panel opens, so this verb is reliable. Each
result is a :class:`CommentItem` (top-level comments; replies carry ``repliesToId``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.capabilities.tiktok.scrape.schemas import (
    MAX_TIKTOK_ITEMS,
    MAX_TIKTOK_SOURCES,
)
from app.proprietary.platforms.tiktok import CommentItem


class CommentsInput(BaseModel):
    video_urls: list[str] = Field(
        min_length=1,
        max_length=MAX_TIKTOK_SOURCES,
        description="TikTok video URLs (/@<user>/video/<id>) to pull comments from.",
    )
    comments_per_video: int = Field(
        default=20,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max comments to return per video.",
    )
    max_items: int = Field(
        default=20,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max total comments to return across all videos.",
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable comments for the pre-flight gate: ``max_items`` is a
        hard cross-video ceiling (le=100), so no call can exceed it."""
        return self.max_items


class CommentsOutput(BaseModel):
    items: list[CommentItem] = Field(
        default_factory=list,
        description="One item per comment returned, in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned comment = one billable unit; ErrorItems (``errorCode`` set,
        for bad URLs or empty/withheld videos) are surfaced but never charged."""
        return sum(1 for item in self.items if not getattr(item, "errorCode", None))
