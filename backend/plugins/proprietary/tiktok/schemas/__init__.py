"""Apify-compatible input and output contracts for the TikTok scraper."""

from __future__ import annotations

from .input import StartUrl, TikTokScrapeInput
from .items import (
    AuthorMeta,
    CommentItem,
    ErrorItem,
    MusicMeta,
    TikTokProfileItem,
    TikTokVideoItem,
    VideoMeta,
)

__all__ = [
    "AuthorMeta",
    "CommentItem",
    "ErrorItem",
    "MusicMeta",
    "StartUrl",
    "TikTokProfileItem",
    "TikTokScrapeInput",
    "TikTokVideoItem",
    "VideoMeta",
]
