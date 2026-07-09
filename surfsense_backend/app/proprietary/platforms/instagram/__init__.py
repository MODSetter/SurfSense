"""Platform-native Instagram scraper (anonymous, no browser)."""

from .fetch import InstagramAccessBlockedError
from .schemas import (
    InstagramComment,
    InstagramHashtag,
    InstagramMediaItem,
    InstagramPlace,
    InstagramProfile,
    InstagramScrapeInput,
)
from .scraper import iter_instagram, scrape_instagram

__all__ = [
    "InstagramAccessBlockedError",
    "InstagramComment",
    "InstagramHashtag",
    "InstagramMediaItem",
    "InstagramPlace",
    "InstagramProfile",
    "InstagramScrapeInput",
    "iter_instagram",
    "scrape_instagram",
]
