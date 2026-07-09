"""Cookie-warmed, rotate-on-block proxy session and page-fetch seam."""

from __future__ import annotations

from .client import fetch_html
from .errors import TikTokAccessBlockedError
from .listing import fetch_comments, fetch_item_list, fetch_user_search
from .proxy import bind_proxy_holder, open_proxy_holder, proxy_session

__all__ = [
    "TikTokAccessBlockedError",
    "bind_proxy_holder",
    "fetch_comments",
    "fetch_html",
    "fetch_item_list",
    "fetch_user_search",
    "open_proxy_holder",
    "proxy_session",
]
