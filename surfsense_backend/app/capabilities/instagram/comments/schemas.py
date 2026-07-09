"""``instagram.comments`` I/O contracts.

A lean surface over ``InstagramScrapeInput`` (``resultsType="comments"``). The
scraper's ``InstagramComment`` is reused verbatim as the output element.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.capabilities.instagram.scrape.schemas import (
    MAX_INSTAGRAM_ITEMS,
    MAX_INSTAGRAM_SOURCES,
)
from app.proprietary.platforms.instagram import InstagramComment

MAX_COMMENTS_PER_POST = 50
"""Anonymous web media pages surface at most ~50 comments per post."""


class CommentsInput(BaseModel):
    urls: list[str] = Field(
        min_length=1,
        max_length=MAX_INSTAGRAM_SOURCES,
        description="Post or reel URLs to fetch comments for (shortCode or numeric-ID forms).",
    )
    newest_first: bool = Field(
        default=False,
        description="Return newest comments first.",
    )
    include_replies: bool = Field(
        default=False,
        description="Include nested replies; each reply is a separate billable item.",
    )
    max_comments_per_post: int = Field(
        default=10,
        ge=1,
        le=MAX_COMMENTS_PER_POST,
        description="Max comments per post (Instagram caps at 50).",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_INSTAGRAM_ITEMS,
        description="Max total comments to return across all posts.",
    )

    @property
    def estimated_units(self) -> int:
        return self.max_items


class CommentsOutput(BaseModel):
    items: list[InstagramComment] = Field(
        default_factory=list,
        description="One item per comment (or reply), in emission order.",
    )

    @property
    def billable_units(self) -> int:
        return len(self.items)
