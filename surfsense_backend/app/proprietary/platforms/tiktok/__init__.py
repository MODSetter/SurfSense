"""Anonymous, blob-first TikTok scraper (public interface).

The capability layer depends only on the names re-exported here: the input
schema, the collector/generator, the video item shape, and the hard-block error.
"""

from __future__ import annotations

from .orchestrator import iter_tiktok, scrape_tiktok, search_tiktok_users
from .schemas import TikTokProfileItem, TikTokScrapeInput, TikTokVideoItem
from .session import TikTokAccessBlockedError

__all__ = [
    "TikTokAccessBlockedError",
    "TikTokProfileItem",
    "TikTokScrapeInput",
    "TikTokVideoItem",
    "iter_tiktok",
    "scrape_tiktok",
    "search_tiktok_users",
]
