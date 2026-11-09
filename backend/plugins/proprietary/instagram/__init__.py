"""Platform-native Instagram scraper (anonymous, no browser)."""

from .fetch import InstagramAccessBlockedError
from .schemas import (
    InstagramMediaItem,
    InstagramProfile,
    InstagramScrapeInput,
)
from .scraper import iter_instagram, scrape_instagram

__all__ = [
    "InstagramAccessBlockedError",
    "InstagramMediaItem",
    "InstagramProfile",
    "InstagramScrapeInput",
    "iter_instagram",
    "scrape_instagram",
]
