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


class ProxyProvider(ABC):
    """Interface every proxy provider must implement."""

    #: Unique key used to select this provider via the ``PROXY_PROVIDER`` env var.
    name: str = "base"

    @abstractmethod
    def get_proxy_url(self) -> str | None:
        """Return ``http://user:pass@host:port`` (no trailing slash), or ``None``.

        This is the canonical form Scrapling/curl_cffi consume directly.
        """

    @abstractmethod
    def get_playwright_proxy(self) -> dict[str, str] | None:
        """Return a Playwright proxy dict, or ``None`` when not configured."""

    def get_requests_proxies(self) -> dict[str, str] | None:
        """Return a ``requests``/``aiohttp`` proxies dict, or ``None``.

        Built from :meth:`get_proxy_url` by default; override if a provider needs
        different http vs https endpoints.
        """
        proxy_url = self.get_proxy_url()
        if proxy_url is None:
            return None
        return {"http": proxy_url, "https": proxy_url}

    @property
    def is_pool_backed(self) -> bool:
        """Whether this provider rotates across a *client-side* pool of endpoints.

        ``False`` for single-endpoint providers (including server-side rotating
        gateways like ``anonymous_proxies``, whose rotation happens upstream).
        The crawler performs its bounded proxy-error rotation-retry **only** when
        this is ``True`` — retrying a single static endpoint would just re-hit the
        same dead proxy.
        """
        return False
