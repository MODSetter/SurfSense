# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Reddit scraper.

The MVP populates a reliably-sourced subset of fields; every other output field
is emitted as ``None``/``[]`` so the contract can expand additively.

**Anonymous only.** There is deliberately **no** authentication field on the
input (no username/password/token/``login*``) — the scraper holds only Reddit's
anonymous ``loid`` session cookie and can never log in. Anything auth-shaped a
caller sends lands in ``extra`` and is ignored.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RedditSort = Literal["relevance", "hot", "top", "new", "rising", "comments"]
RedditTime = Literal["all", "hour", "day", "week", "month", "year"]
RedditDataType = Literal["post", "comment", "community", "user"]


class StartUrl(BaseModel):
    """A single direct URL entry (``{"url": ...}``; extra keys ignored)."""

    model_config = ConfigDict(extra="allow")

    url: str


class RedditScrapeInput(BaseModel):
    """Reddit scraper input surface (anonymous, no auth fields).

    Caps (``maxItems``/``maxPostCount``/...) are collector policy applied by
    :func:`scrape_reddit`, NOT ceilings baked into the streaming flows. Fields
    the MVP doesn't act on are still accepted via ``extra="allow"`` for parity.
    """

    model_config = ConfigDict(extra="allow")

    # Discovery
    startUrls: list[StartUrl] = Field(default_factory=list)
    searches: list[str] = Field(default_factory=list)
    searchCommunityName: str | None = None

    # Sort / filter
    sort: RedditSort = "new"
    time: RedditTime | None = None
    includeNSFW: bool = True

    # Skips
    skipComments: bool = False
    skipUserPosts: bool = False
    skipCommunity: bool = False

    # Caps (collector policy; enforced by scrape_reddit, not the flows)
    maxItems: int = Field(default=10, ge=0)
    maxPostCount: int = Field(default=10, ge=0)
    maxComments: int = Field(default=10, ge=0)
    maxCommunitiesCount: int = Field(default=2, ge=0)
    maxUserCount: int = Field(default=2, ge=0)

    # Incremental scraping (ISO dates)
    postDateLimit: str | None = None
    commentDateLimit: str | None = None


class RedditItem(BaseModel):
    """Single flat output item, keyed by ``dataType``.

    One model for post/comment/community/user (union of fields, unsourced
    default ``None``/``[]``), using a single flat-dataset shape.
    ``extra="allow"`` keeps the contract open so added fields never break
    consumers.
    """

    model_config = ConfigDict(extra="allow")

    dataType: RedditDataType | None = None

    # Identity / provenance
    id: str | None = None
    parsedId: str | None = None
    url: str | None = None
    username: str | None = None
    userId: str | None = None

    # Content
    title: str | None = None
    body: str | None = None
    html: str | None = None
    link: str | None = None
    externalUrl: str | None = None

    # Community
    communityName: str | None = None
    parsedCommunityName: str | None = None
    numberOfMembers: int | None = None

    # Engagement
    numberOfComments: int | None = None
    numberOfReplies: int | None = None
    upVotes: int | None = None
    upVoteRatio: float | None = None

    # Flags / media
    over18: bool | None = None
    isVideo: bool | None = None
    flair: str | None = None
    authorFlair: str | None = None
    thumbnailUrl: str | None = None
    imageUrls: list[str] = Field(default_factory=list)
    videoUrls: list[str] = Field(default_factory=list)

    # Threading
    postId: str | None = None
    parentId: str | None = None

    # Timestamps
    createdAt: str | None = None
    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat output dict shape (keeps extras)."""
        return self.model_dump(exclude_none=False)
