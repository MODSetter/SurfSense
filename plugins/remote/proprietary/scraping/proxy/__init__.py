"""Modular residential / rotating proxy provider package.

Selects a provider via the ``SCRAPING_PROXY_PROVIDER`` env var (see ``registry.py``) and
exposes proxy settings in the formats different HTTP libraries expect. Add new
vendors by implementing :class:`ProxyProvider` in ``providers/`` and registering
them in ``registry.py``.
"""

from proprietary.scraping.proxy.base import ProxyProvider
from proprietary.scraping.proxy.registry import get_active_provider


def get_proxy_url() -> str | None:
    """Canonical ``http://`` URL, with user, password, host and port, for Scrapling/curl_cffi."""
    return get_active_provider().get_proxy_url()


def get_geo_proxy_url(country: str | None = None) -> str | None:
    """Proxy URL pinned to an exit country when the provider supports it."""
    return get_active_provider().get_geo_proxy_url(country)


def get_sticky_proxy_url(session_id: str, country: str | None = None) -> str | None:
    """Proxy URL pinned to a stable vendor session when supported."""
    return get_active_provider().get_sticky_proxy_url(session_id, country)


def get_playwright_proxy() -> dict[str, str] | None:
    """Playwright-style proxy dict, or ``None`` when not configured."""
    return get_active_provider().get_playwright_proxy()


def get_requests_proxies() -> dict[str, str] | None:
    """``{"http": ..., "https": ...}`` dict for requests/aiohttp, or ``None``."""
    return get_active_provider().get_requests_proxies()


def get_residential_proxy_url() -> str | None:
    """Backward-compatible alias for :func:`get_proxy_url`."""
    return get_proxy_url()


__all__ = [
    "ProxyProvider",
    "get_active_provider",
    "get_geo_proxy_url",
    "get_playwright_proxy",
    "get_proxy_url",
    "get_requests_proxies",
    "get_residential_proxy_url",
    "get_sticky_proxy_url",
]
