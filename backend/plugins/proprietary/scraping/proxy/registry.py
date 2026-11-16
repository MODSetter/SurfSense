"""Proxy provider registry.

Maps ``SCRAPING_PROXY_PROVIDER`` to the vendor whose URL format the scrapers
rewrite for sticky sessions and countries. Unset, they scrape direct, as in
development and tests. To add a vendor: implement a provider in ``providers/``
and add it to ``_PROVIDERS`` below.
"""

import logging

from proprietary.scraping.config import Config
from proprietary.scraping.proxy.base import ProxyProvider
from proprietary.scraping.proxy.providers.dataimpulse import DataImpulseProvider
from proprietary.scraping.proxy.providers.nodemaven import NodeMavenProvider

logger = logging.getLogger(__name__)

# Registered proxy providers, keyed by their ``name``.
_PROVIDERS: dict[str, type[ProxyProvider]] = {
    DataImpulseProvider.name: DataImpulseProvider,
    NodeMavenProvider.name: NodeMavenProvider,
}


class _Direct(ProxyProvider):
    """No vendor configured: every scrape goes from the container's own address."""

    name = ""

    def get_proxy_url(self) -> str | None:
        return None


_active_provider: ProxyProvider | None = None


def get_active_provider() -> ProxyProvider:
    """The configured provider, cached for the process.

    An unknown name is an error rather than a fallback: SurfSense hosts these
    scrapers itself, and a typo must not quietly scrape without a proxy.
    """
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    key = (Config.PROXY_PROVIDER or "").strip()
    if not key:
        _active_provider = _Direct()
        return _active_provider
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        raise ValueError(
            f"Unknown SCRAPING_PROXY_PROVIDER '{key}'. "
            f"Available: {', '.join(sorted(_PROVIDERS))}"
        )
    _active_provider = provider_cls()
    if _active_provider.get_proxy_url() is None:
        logger.warning(
            "SCRAPING_PROXY_PROVIDER='%s' but SCRAPING_PROXY_URL is unset; "
            "scrapes will run without a proxy.",
            key,
        )
    return _active_provider
