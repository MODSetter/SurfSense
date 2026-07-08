"""Apify-compatible input and output contracts for the TikTok scraper."""

from __future__ import annotations

from .items import (
    AuthorMeta,
    CommentItem,
    ErrorItem,
    MusicMeta,
    TikTokVideoItem,
    VideoMeta,
)

__all__ = [
    "AuthorMeta",
    "CommentItem",
    "ErrorItem",
    "MusicMeta",
    "TikTokVideoItem",
    "VideoMeta",
]
