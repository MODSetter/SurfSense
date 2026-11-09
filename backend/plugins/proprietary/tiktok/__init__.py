"""Anonymous, blob-first TikTok scraper (public interface).

The plugin's server depends only on the names re-exported here: the input
schema, the collector/generator, the video item shape, the hard-block error, the
progress hook, and the browser warm-up.
"""

from __future__ import annotations

from .orchestrator import (
    iter_tiktok,
    scrape_tiktok,
    scrape_tiktok_comments,
    scrape_tiktok_trending,
    search_tiktok_users,
)
from .schemas import (
    CommentItem,
    TikTokProfileItem,
    TikTokScrapeInput,
    TikTokVideoItem,
)
from .session import TikTokAccessBlockedError, on_stage, warm_browser

__all__ = [
    "CommentItem",
    "TikTokAccessBlockedError",
    "TikTokProfileItem",
    "TikTokScrapeInput",
    "TikTokVideoItem",
    "iter_tiktok",
    "on_stage",
    "scrape_tiktok",
    "scrape_tiktok_comments",
    "scrape_tiktok_trending",
    "search_tiktok_users",
    "warm_browser",
]
