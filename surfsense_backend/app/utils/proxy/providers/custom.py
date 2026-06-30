"""Bring-your-own (BYO) custom proxy provider.

Reads one or more proxy endpoints from env (``CUSTOM_PROXY_URL`` and/or the
comma-separated ``CUSTOM_PROXY_URLS``). With a single endpoint it behaves like a
static proxy; with a pool (>1) it rotates client-side via Scrapling's thread-safe
``ProxyRotator`` (cyclic), transparently to every caller of the zero-arg getters.

No vendor-specific auth assumptions: a user who wants a specific vendor points
``CUSTOM_PROXY_URLS`` at that vendor's ``http://user:pass@host:port`` endpoints.
"""

import logging
from urllib.parse import urlsplit

from scrapling.engines.toolbelt import ProxyRotator

from app.config import Config
from app.utils.proxy.base import ProxyProvider

logger = logging.getLogger(__name__)


class CustomProxyProvider(ProxyProvider):
    """BYO provider for a single endpoint or a rotating pool of endpoints."""

    name = "custom"

    def __init__(self) -> None:
        self._urls = self._load_urls()
        # Only build a rotator for an actual pool; a single endpoint stays static.
        self._rotator = ProxyRotator(self._urls) if len(self._urls) > 1 else None
        if not self._urls:
            logger.warning(
                "PROXY_PROVIDER='custom' selected but neither CUSTOM_PROXY_URL nor "
                "CUSTOM_PROXY_URLS is set; crawls will run without a proxy."
            )

    @staticmethod
    def _load_urls() -> list[str]:
        """Collect proxy URLs from env (pool first, then single), de-duplicated."""
        urls: list[str] = []
        pool = Config.CUSTOM_PROXY_URLS
        if pool:
            urls.extend(part.strip() for part in pool.split(",") if part.strip())

        single = (Config.CUSTOM_PROXY_URL or "").strip()
        if single and single not in urls:
            urls.append(single)

        return urls

    @property
    def is_pool_backed(self) -> bool:
        return self._rotator is not None

    def get_proxy_url(self) -> str | None:
        if not self._urls:
            return None
        if self._rotator is not None:
            # Advances the cyclic index on every call (thread-safe).
            return self._rotator.get_proxy()
        return self._urls[0]

    def get_playwright_proxy(self) -> dict[str, str] | None:
        proxy_url = self.get_proxy_url()
        if not proxy_url:
            return None

        parts = urlsplit(proxy_url)
        if not parts.hostname:
            return None

        server = f"{parts.scheme or 'http'}://{parts.hostname}"
        if parts.port:
            server = f"{server}:{parts.port}"

        proxy: dict[str, str] = {"server": server}
        if parts.username:
            proxy["username"] = parts.username
        if parts.password:
            proxy["password"] = parts.password
        return proxy
