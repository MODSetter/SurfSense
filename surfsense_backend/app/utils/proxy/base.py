"""Abstract base class for residential / rotating proxy providers.

Each provider reads its own credentials from the application Config and exposes
proxy settings in the formats the different HTTP stacks expect:

* ``get_proxy_url`` -> canonical ``http://user:pass@host:port`` string consumed
  by Scrapling's fetchers (curl_cffi / patchright / camoufox).
* ``get_requests_proxies`` -> ``{"http": ..., "https": ...}`` dict for
  ``requests`` / ``aiohttp``.
* ``get_playwright_proxy`` -> Playwright-style ``{"server", "username",
  "password"}`` dict.

Add a new vendor by subclassing :class:`ProxyProvider` in ``providers/`` and
registering it in ``registry.py``.
"""

from abc import ABC, abstractmethod
from urllib.parse import urlsplit


class ProxyProvider(ABC):
    """Interface every proxy provider must implement."""

    #: Unique key used to select this provider via the ``PROXY_PROVIDER`` env var.
    name: str = "base"

    @abstractmethod
    def get_proxy_url(self) -> str | None:
        """Return ``http://user:pass@host:port`` (no trailing slash), or ``None``.

        This is the canonical form Scrapling/curl_cffi consume directly, and the
        single source every provider must supply — the ``requests`` and Playwright
        shapes below are derived from it.
        """

    def get_playwright_proxy(self) -> dict[str, str] | None:
        """Return a Playwright ``{"server","username","password"}`` dict, or ``None``.

        Parsed from :meth:`get_proxy_url` (the canonical URL) by default, since
        every provider's credentials already live in that URL. Override only for a
        vendor whose Playwright form can't be expressed as a parse of the URL.
        """
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

    def get_requests_proxies(self) -> dict[str, str] | None:
        """Return a ``requests``/``aiohttp`` proxies dict, or ``None``.

        Built from :meth:`get_proxy_url` by default; override if a provider needs
        different http vs https endpoints.
        """
        proxy_url = self.get_proxy_url()
        if proxy_url is None:
            return None
        return {"http": proxy_url, "https": proxy_url}

    def get_geo_proxy_url(self, country: str | None = None) -> str | None:
        """Return a proxy URL pinned to ``country`` when supported.

        Providers without vendor-specific country routing safely fall back to
        their ordinary proxy URL.
        """
        return self.get_proxy_url()

    def get_sticky_proxy_url(
        self, session_id: str, country: str | None = None
    ) -> str | None:
        """Return a proxy URL pinned to ``session_id`` when supported.

        Providers without vendor-specific session routing safely fall back to
        their ordinary proxy URL.
        """
        return self.get_geo_proxy_url(country)

    def get_location(self) -> str:
        """Return the proxy's configured exit region (e.g. ``"us"``), or ``""``.

        Vendor-agnostic hook the crawler's geoip-match (``03e``) uses to align the
        browser locale/timezone with the exit IP's country. Default ``""``
        (unknown) for providers that don't pin a region (e.g. BYO ``custom`` URLs,
        where the region is baked opaquely into the URL). Override in providers
        that hold the region as a discrete field.
        """
        return ""

    @property
    def is_pool_backed(self) -> bool:
        """Whether this provider rotates across a *client-side* pool of endpoints.

        ``False`` for single-endpoint providers (including server-side rotating
        gateways like ``dataimpulse``, whose rotation happens upstream). The
        crawler performs its bounded proxy-error rotation-retry **only** when this
        is ``True`` — retrying a single static endpoint would just re-hit the same
        dead proxy.
        """
        return False
