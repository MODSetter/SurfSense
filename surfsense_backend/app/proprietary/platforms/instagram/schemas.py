# ruff: noqa: N815
"""Input/output models for the Instagram scraper.

The models mirror the public Instagram scraper actor spec so the endpoint can be
a drop-in: the input accepts the full documented surface, and every output field
is emitted (``None``/``[]`` when the anonymous web endpoints cannot source it
yet) so the contract expands additively — the same rule the Google Search and
YouTube models follow.

**Anonymous only.** There is deliberately **no** authentication field on the
input (no username/password/token/cookie/``login*``) — the scraper holds only
Instagram's anonymous web-session cookies (``csrftoken``/``mid``) and can never
log in. Anything auth-shaped a caller sends lands in ``extra`` and is ignored.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InstagramResultsType = Literal[
    "posts", "details", "comments", "reels", "mentions", "stories"
]
InstagramSearchType = Literal["hashtag", "profile", "place", "user"]
InstagramDetailKind = Literal["profile", "hashtag", "place"]


class InstagramScrapeInput(BaseModel):
    """Instagram scraper input surface (anonymous, no auth fields).

    Field names mirror the public actor spec verbatim. ``resultsLimit`` /
    ``searchLimit`` are collector policy applied by :func:`scrape_instagram`,
    NOT ceilings baked into the streaming flows. Fields the acquisition layer
    doesn't source yet are still accepted via ``extra="allow"`` for parity.
    """

    model_config = ConfigDict(extra="allow")
    resultsType: InstagramResultsType = "posts"
    directUrls: list[str] = Field(default_factory=list)
    resultsLimit: int | None = Field(default=None, ge=1)
    onlyPostsNewerThan: str | None = None
    search: str | None = None
    searchType: InstagramSearchType = "hashtag"
    searchLimit: int | None = Field(default=None, ge=1, le=250)
    addParentData: bool = False
    skipPinnedPosts: bool = False
    isNewestComments: bool = False
    includeNestedComments: bool = False
    addProfileStatistics: bool = False


class _ItemBase(BaseModel):
    """Common error / provenance fields carried on every output item.

    Errors surface as item-level fields (never exceptions) so a partial run
    still returns the items it could source, mirroring the actor's shape.
    """

    model_config = ConfigDict(extra="allow")
    inputUrl: str | None = None
    error: str | None = None
    errorDescription: str | None = None
    requestErrorMessages: list[str] = Field(default_factory=list)

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat output dict shape (keeps extras)."""
        return self.model_dump(exclude_none=False)


class InstagramMediaItem(_ItemBase):
    """A post / reel / mention. One flat schema per the actor FAQ."""

    id: str | None = None
    type: Literal["Image", "Video", "Sidecar"] | None = None
    shortCode: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    url: str | None = None
    commentsCount: int | None = None
    firstComment: str | None = None
    latestComments: list[dict[str, Any]] = Field(default_factory=list)
    dimensionsHeight: int | None = None
    dimensionsWidth: int | None = None
    displayUrl: str | None = None
    images: list[str] = Field(default_factory=list)
    videoUrl: str | None = None
    alt: str | None = None
    likesCount: int | None = None
    videoViewCount: int | None = None
    videoPlayCount: int | None = None
    reshareCount: int | None = None
    timestamp: str | None = None
    childPosts: list[dict[str, Any]] = Field(default_factory=list)
    ownerUsername: str | None = None
    ownerId: str | None = None
    ownerFullName: str | None = None
    isPinned: bool | None = None
    productType: str | None = None
    videoDuration: float | None = None
    paidPartnership: bool | None = None
    taggedUsers: list[dict[str, Any]] = Field(default_factory=list)
    musicInfo: dict[str, Any] | None = None
    coauthorProducers: list[dict[str, Any]] = Field(default_factory=list)
    locationName: str | None = None
    locationId: str | None = None
    isCommentsDisabled: bool | None = None
    dataSource: dict[str, Any] | None = None


class InstagramComment(_ItemBase):
    """A comment on a post / reel."""

    id: str | None = None
    postUrl: str | None = None
    commentUrl: str | None = None
    text: str | None = None
    ownerUsername: str | None = None
    ownerProfilePicUrl: str | None = None
    timestamp: str | None = None
    repliesCount: int | None = None
    replies: list[dict[str, Any]] = Field(default_factory=list)
    likesCount: int | None = None
    owner: dict[str, Any] | None = None


class InstagramProfile(_ItemBase):
    """A profile detail item (``detailKind = "profile"``)."""

    detailKind: Literal["profile"] = "profile"
    id: str | None = None
    username: str | None = None
    url: str | None = None
    fullName: str | None = None
    biography: str | None = None
    externalUrl: str | None = None
    followersCount: int | None = None
    followsCount: int | None = None
    postsCount: int | None = None
    highlightReelCount: int | None = None
    igtvVideoCount: int | None = None
    isBusinessAccount: bool | None = None
    businessCategoryName: str | None = None
    private: bool | None = None
    verified: bool | None = None
    profilePicUrl: str | None = None
    profilePicUrlHD: str | None = None
    relatedProfiles: list[dict[str, Any]] = Field(default_factory=list)
    latestPosts: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] | None = None


class InstagramHashtag(_ItemBase):
    """A hashtag detail item (``detailKind = "hashtag"``)."""

    detailKind: Literal["hashtag"] = "hashtag"
    id: str | None = None
    name: str | None = None
    url: str | None = None
    postsCount: int | None = None
    topPosts: list[dict[str, Any]] = Field(default_factory=list)
    posts: list[dict[str, Any]] = Field(default_factory=list)
    related: list[dict[str, Any]] = Field(default_factory=list)
    searchTerm: str | None = None
    searchSource: str | None = None


class InstagramPlace(_ItemBase):
    """A place detail item (``detailKind = "place"``)."""

    detailKind: Literal["place"] = "place"
    name: str | None = None
    location_id: str | None = None
    slug: str | None = None
    lat: float | None = None
    lng: float | None = None
    location_address: str | None = None
    location_city: str | None = None
    location_zip: str | None = None
    phone: str | None = None
    website: str | None = None
    category: str | None = None
    media_count: int | None = None
    posts: list[dict[str, Any]] = Field(default_factory=list)
    searchTerm: str | None = None
    searchSource: str | None = None
