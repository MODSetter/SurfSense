"""Backward-compatible shim for the proxy helpers.

The implementation now lives in the modular :mod:`app.utils.proxy` package.
Existing imports of ``app.utils.proxy_config`` keep working via these re-exports.
Prefer importing from ``app.utils.proxy`` (and ``get_proxy_url``) in new code.
"""

from app.utils.proxy import (
    get_playwright_proxy,
    get_proxy_url,
    get_requests_proxies,
    get_residential_proxy_url,
)

__all__ = [
    "get_playwright_proxy",
    "get_proxy_url",
    "get_requests_proxies",
    "get_residential_proxy_url",
]
