"""Platform-native YouTube scraper (Apify YouTube Scraper-compatible)."""

from .comments import iter_comments, scrape_comments
from .schemas import CommentItem, VideoItem, YouTubeCommentsInput, YouTubeScrapeInput
from .scraper import iter_youtube, scrape_youtube

__all__ = [
    "CommentItem",
    "VideoItem",
    "YouTubeCommentsInput",
    "YouTubeScrapeInput",
    "iter_comments",
    "iter_youtube",
    "scrape_comments",
    "scrape_youtube",
]
