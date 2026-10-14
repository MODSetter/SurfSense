"""Cookie-warmed, rotate-on-block proxy session and page-fetch seam."""

from __future__ import annotations

from .client import fetch_html
from .errors import TikTokAccessBlockedError
from .listing import (
    fetch_comments,
    fetch_item_list,
    fetch_trending,
    fetch_user_search,
    warm_browser,
)
from .proxy import on_stage, proxy_session

__all__ = [
    "TikTokAccessBlockedError",
    "fetch_comments",
    "fetch_html",
    "fetch_item_list",
    "fetch_trending",
    "fetch_user_search",
    "on_stage",
    "proxy_session",
    "warm_browser",
]
