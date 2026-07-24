"""``reddit.scrape`` I/O contracts.

A lean, agent-friendly surface over ``RedditScrapeInput``
(``app/proprietary/platforms/reddit``). The executor maps this to the full
scraper input; the scraper's ``RedditItem`` is reused verbatim as the output
element.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.capabilities.core.validation import HttpUrlStr
from app.proprietary.platforms.reddit import RedditItem
from app.proprietary.platforms.reddit.schemas import RedditSort, RedditTime

MAX_REDDIT_SOURCES = 20
"""Per-call cap on urls + search_queries: bounds a synchronous request's fan-out."""

MAX_REDDIT_ITEMS = 100
"""Hard ceiling on items returned per call, regardless of the per-target caps."""


class ScrapeInput(BaseModel):
    urls: list[HttpUrlStr] = Field(
        default_factory=list,
        max_length=MAX_REDDIT_SOURCES,
        description=(
            "Reddit URLs to scrape: a post, a subreddit (/r/<name>), a user "
            "(/user/<name>), or a search URL. Provide these OR search_queries/"
            "community (at least one source is required)."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_REDDIT_SOURCES,
        description=(
            "Search terms to run on Reddit; each returns up to max_items results. "
            "Scope to one subreddit with community."
        ),
    )
    community: str | None = Field(
        default=None,
        description=(
            "Subreddit name (without 'r/') to scope search_queries to, e.g. "
            "'python'. With no search_queries, its listing is scraped."
        ),
    )
    sort: RedditSort = Field(
        default="new",
        description="Result ordering: relevance, hot, top, new, rising, or comments.",
    )
    time_filter: RedditTime | None = Field(
        default=None,
        description="Time window for 'top'/'controversial' sorts: hour, day, week, month, year, all.",
    )
    include_nsfw: bool = Field(
        default=True,
        description="Include posts flagged over-18 (NSFW) in the results.",
    )
    skip_comments: bool = Field(
        default=False,
        description="Skip fetching comment trees (faster; posts/listings only).",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_REDDIT_ITEMS,
        description="Max total items to return across all sources.",
    )
    max_posts: int = Field(
        default=10,
        ge=0,
        description="Max posts to pull per subreddit/user/search target.",
    )
    max_comments: int = Field(
        default=10,
        ge=0,
        description="Max comments to pull per post (0 = none).",
    )
    post_date_limit: str | None = Field(
        default=None,
        description="ISO date; only return posts newer than this (incremental scrape).",
    )
    comment_date_limit: str | None = Field(
        default=None,
        description="ISO date; only return comments newer than this (incremental scrape).",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ScrapeInput:
        if not self.urls and not self.search_queries and not self.community:
            raise ValueError(
                "Provide at least one of 'urls', 'search_queries', or 'community'."
            )
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate: ``max_items`` is a
        hard cross-source ceiling (le=100), so no call can exceed it."""
        return self.max_items


class ScrapeOutput(BaseModel):
    items: list[RedditItem] = Field(
        default_factory=list,
        description="One item per result (post/comment/community/user), in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned item = one billable unit."""
        return len(self.items)
