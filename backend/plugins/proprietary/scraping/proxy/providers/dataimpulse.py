"""DataImpulse residential / rotating proxy provider.

Takes the shared ``SCRAPING_PROXY_URL`` env, pasted straight from the vendor
dashboard, and layers the vendor's knowledge on top of that URL:

* :meth:`get_location` reads DataImpulse's ``__cr.<country>`` username suffix so
  the crawler's geoip-match can align the browser locale with the exit country.

Rotation happens server-side: a fresh exit IP per request on the default pool
port.

Example URL::

    http://<token>__cr.us:<password>@gw.dataimpulse.com:823

A sticky session is a port: each of 10000 to 20000 holds one exit IP, with or
without a country. DataImpulse ignores a session id in the username and still
rotates per request (measured live, 2026-10-12), so the session id picks the port.
"""

import hashlib
import logging
import re
from urllib.parse import quote, urlsplit, urlunsplit

from proprietary.scraping.config import Config
from proprietary.scraping.proxy.base import ProxyProvider

logger = logging.getLogger(__name__)

# DataImpulse encodes country routing as a "__cr.<country>" username suffix; the
# country token runs until the next "__" param (e.g. "__sid") or the end.
_COUNTRY_MARKER = "__cr."
_COUNTRY_RE = re.compile(r"__cr\.[A-Za-z]{2,}")
_SESSION_RE = re.compile(r"__sid\.[A-Za-z0-9_-]+")
# Each port in this range is one sticky exit IP.
_STICKY_PORTS = range(10000, 20001)


def _sticky_port(session_id: str) -> int:
    """The same session always lands on the same port, so on the same IP."""
    if not re.search(r"[A-Za-z0-9]", session_id):
        raise ValueError("session_id must contain at least one letter or digit")
    digest = int.from_bytes(hashlib.sha256(session_id.encode()).digest()[:8], "big")
    return _STICKY_PORTS[digest % len(_STICKY_PORTS)]


def _safe_country(country: str | None) -> str | None:
    if country is None:
        return None
    safe_country = re.sub(r"[^a-z]", "", country.lower())
    return safe_country or None


class DataImpulseProvider(ProxyProvider):
    """Provider for a DataImpulse proxy URL in the shared ``SCRAPING_PROXY_URL`` env."""

    name = "dataimpulse"

    def get_proxy_url(self) -> str | None:
        url = (Config.PROXY_URL or "").strip()
        return url or None

    def get_location(self) -> str:
        """Country parsed from the ``__cr.<country>`` username suffix, or ``""``."""
        url = self.get_proxy_url()
        if not url:
            return ""
        username = urlsplit(url).username or ""
        if _COUNTRY_MARKER not in username:
            return ""
        return username.split(_COUNTRY_MARKER, 1)[1].split("__", 1)[0].lower()

    def _rewrite_proxy_url(
        self, *, country: str | None = None, session_id: str | None = None
    ) -> str | None:
        url = self.get_proxy_url()
        if not url:
            return None
        parts = urlsplit(url)
        username = _SESSION_RE.sub("", _COUNTRY_RE.sub("", parts.username or ""))
        safe_country = _safe_country(country)
        if safe_country is not None:
            username += f"__cr.{safe_country}"
        elif _COUNTRY_MARKER in (parts.username or ""):
            username += f"__cr.{self.get_location()}"
        userinfo = quote(username, safe="%")
        if parts.password is not None:
            userinfo += f":{quote(parts.password, safe='%')}"
        host = parts.hostname or ""
        netloc = f"{userinfo}@{host}"
        port = _sticky_port(session_id) if session_id is not None else parts.port
        if port:
            netloc += f":{port}"
        return urlunsplit(
            (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
        )

    def get_geo_proxy_url(self, country: str | None = None) -> str | None:
        """Return the configured URL with a country-routing suffix when requested."""
        if not _safe_country(country):
            return self.get_proxy_url()
        return self._rewrite_proxy_url(country=country)

    def get_sticky_proxy_url(
        self, session_id: str, country: str | None = None
    ) -> str | None:
        """The configured URL on the session's sticky port, with its country."""
        return self._rewrite_proxy_url(country=country, session_id=session_id)

    def sticky_slot(self, session_id: str) -> object:
        """The port, since each port holds one IP.

        About 118 live ids give even odds of two landing on one port; the lease
        keeps live ports distinct.
        """
        return _sticky_port(session_id)
