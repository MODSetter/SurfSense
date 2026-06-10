"""Proxy provider registry.

Maps the ``PROXY_PROVIDER`` config value to a :class:`ProxyProvider`
implementation. To add a new vendor: implement a provider in ``providers/`` and
add a single entry to ``_PROVIDERS`` below - no caller changes required.
"""

import logging

from app.config import Config
from app.utils.proxy.base import ProxyProvider
from app.utils.proxy.providers.anonymous_proxies import AnonymousProxiesProvider

logger = logging.getLogger(__name__)

# Registered proxy providers, keyed by their ``name``.
_PROVIDERS: dict[str, type[ProxyProvider]] = {
    AnonymousProxiesProvider.name: AnonymousProxiesProvider,
}

_DEFAULT_PROVIDER = AnonymousProxiesProvider.name

_active_provider: ProxyProvider | None = None


def get_active_provider() -> ProxyProvider:
    """Return the configured proxy provider instance (cached for the process)."""
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    key = (Config.PROXY_PROVIDER or _DEFAULT_PROVIDER).strip()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        logger.warning(
            "Unknown PROXY_PROVIDER '%s'; falling back to '%s'. Available: %s",
            key,
            _DEFAULT_PROVIDER,
            ", ".join(sorted(_PROVIDERS)),
        )
        provider_cls = _PROVIDERS[_DEFAULT_PROVIDER]

    _active_provider = provider_cls()
    return _active_provider
