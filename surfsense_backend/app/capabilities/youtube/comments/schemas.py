"""``youtube.comments`` I/O contracts.

A lean surface over ``YouTubeCommentsInput``; the scraper's ``CommentItem`` is
reused verbatim as the output element.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.capabilities.core.validation import HttpUrlStr
from app.proprietary.platforms.youtube import CommentItem

MAX_COMMENT_VIDEOS = 20
"""Per-call cap on how many video URLs one request may harvest comments from."""


class CommentsInput(BaseModel):
    urls: list[HttpUrlStr] = Field(
        min_length=1,
        max_length=MAX_COMMENT_VIDEOS,
        description="YouTube video URLs to fetch comments (and replies) for (1-20).",
    )
    max_comments: int = Field(
        default=20,
        ge=1,
        le=100_000,
        description=(
            "Max items returned per video, counting both top-level comments and "
            "their replies."
        ),
    )
    sort_by: Literal["TOP_COMMENTS", "NEWEST_FIRST"] = Field(
        default="NEWEST_FIRST",
        description="Comment ordering: most-liked first, or most-recent first.",
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable comments for the pre-flight gate: up to
        ``max_comments`` per video URL."""
        return len(self.urls) * self.max_comments


class CommentsOutput(BaseModel):
    items: list[CommentItem] = Field(
        default_factory=list,
        description="One item per comment or reply, in the scraper's emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned comment or reply = one billable unit."""
        return len(self.items)
