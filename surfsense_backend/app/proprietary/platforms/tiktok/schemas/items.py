# ruff: noqa: N815 - field names mirror the public camelCase TikTok/Apify API
"""Output items keyed to the Clockworks TikTok actor's shape.

Every model is open (``extra="allow"``) and defaults unsourced fields to
``None``/``[]`` so the MVP can populate a reliable subset and expand the
contract additively without breaking consumers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthorMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    nickName: str | None = None
    profileUrl: str | None = None
    verified: bool | None = None
    signature: str | None = None
    avatar: str | None = None
    privateAccount: bool | None = None
    fans: int | None = None
    following: int | None = None
    heart: int | None = None
    video: int | None = None


class MusicMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    musicId: str | None = None
    musicName: str | None = None
    musicAuthor: str | None = None
    musicOriginal: bool | None = None
    playUrl: str | None = None


class VideoMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    height: int | None = None
    width: int | None = None
    duration: int | None = None
    coverUrl: str | None = None
    format: str | None = None
    definition: str | None = None


class TikTokVideoItem(BaseModel):
    """A single scraped post (video or slideshow)."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    text: str | None = None
    textLanguage: str | None = None
    createTime: int | None = None
    createTimeISO: str | None = None
    isAd: bool | None = None

    authorMeta: AuthorMeta = Field(default_factory=AuthorMeta)
    musicMeta: MusicMeta = Field(default_factory=MusicMeta)
    videoMeta: VideoMeta = Field(default_factory=VideoMeta)

    webVideoUrl: str | None = None
    mediaUrls: list[str] = Field(default_factory=list)

    diggCount: int | None = None
    shareCount: int | None = None
    playCount: int | None = None
    collectCount: int | None = None
    commentCount: int | None = None

    hashtags: list[dict[str, Any]] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)

    isSlideshow: bool | None = None
    isPinned: bool | None = None
    isSponsored: bool | None = None

    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class CommentItem(BaseModel):
    """A single comment or reply under a post."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    text: str | None = None
    videoWebUrl: str | None = None
    diggCount: int | None = None
    replyCommentTotal: int | None = None
    createTime: int | None = None
    createTimeISO: str | None = None

    uid: str | None = None
    uniqueId: str | None = None
    nickName: str | None = None
    avatar: str | None = None

    repliesToId: str | None = None
    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class ErrorItem(BaseModel):
    """Per-input failure, distinguished from normal items by ``errorCode``.

    Mirrors the actor's convention so a private/deleted/empty target surfaces
    as an item instead of silently vanishing from the results.
    """

    model_config = ConfigDict(extra="allow")

    url: str | None = None
    input: str | None = None
    error: str | None = None
    errorCode: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
