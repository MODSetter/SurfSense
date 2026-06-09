"""Modular residential / rotating proxy provider package.

Selects a provider via the ``PROXY_PROVIDER`` env var (see ``registry.py``) and
exposes proxy settings in the formats different HTTP libraries expect. Add new
vendors by implementing :class:`ProxyProvider` in ``providers/`` and registering
them in ``registry.py``.
"""

from app.utils.proxy.base import ProxyProvider
from app.utils.proxy.registry import get_active_provider


def get_proxy_url() -> str | None:
    """Canonical ``http://user:pass@host:port`` URL for Scrapling/curl_cffi."""
    return get_active_provider().get_proxy_url()


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
    "get_playwright_proxy",
    "get_proxy_url",
    "get_requests_proxies",
    "get_residential_proxy_url",
]
