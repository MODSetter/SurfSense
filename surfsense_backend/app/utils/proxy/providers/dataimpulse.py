"""DataImpulse residential / rotating proxy provider.

Takes the shared ``PROXY_URL`` env, exactly like the BYO ``custom`` provider —
the format is uniform, paste it straight from the vendor dashboard. What makes
this a *named* provider rather than just ``custom`` is the vendor-specific
knowledge it layers on top of that URL:

* :meth:`get_location` reads DataImpulse's ``__cr.<country>`` username suffix so
  the crawler's geoip-match can align the browser locale with the exit country
  (``custom`` can't — it treats the URL as opaque).

Rotation happens server-side (a fresh exit IP per request on the default pool
port), so this is NOT :pyattr:`~ProxyProvider.is_pool_backed`.

Example URL::

    http://<token>__cr.us:<password>@gw.dataimpulse.com:823

Sticky sessions use the vendor's ``__sid.<id>`` username suffix, allowing a
caller to keep cookies and requests on the same exit IP.
"""

import logging
import re
from urllib.parse import quote, urlsplit, urlunsplit

from app.config import Config
from app.utils.proxy.base import ProxyProvider

logger = logging.getLogger(__name__)

# DataImpulse encodes country routing as a "__cr.<country>" username suffix; the
# country token runs until the next "__" param (e.g. "__sid") or the end.
_COUNTRY_MARKER = "__cr."
_COUNTRY_RE = re.compile(r"__cr\.[A-Za-z]{2,}")
_SESSION_RE = re.compile(r"__sid\.[A-Za-z0-9_-]+")


def _safe_session_id(session_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", session_id).strip("-")
    if not safe_id:
        raise ValueError("session_id must contain at least one letter or digit")
    return safe_id


def _safe_country(country: str | None) -> str | None:
    if country is None:
        return None
    safe_country = re.sub(r"[^a-z]", "", country.lower())
    return safe_country or None


class DataImpulseProvider(ProxyProvider):
    """Provider for a DataImpulse proxy URL in the shared ``PROXY_URL`` env."""

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
        if session_id is not None:
            username += f"__sid.{_safe_session_id(session_id)}"
        userinfo = quote(username, safe="%")
        if parts.password is not None:
            userinfo += f":{quote(parts.password, safe='%')}"
        host = parts.hostname or ""
        netloc = f"{userinfo}@{host}"
        if parts.port:
            netloc += f":{parts.port}"
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
        """Return the configured URL with deterministic country/session suffixes."""
        return self._rewrite_proxy_url(country=country, session_id=session_id)
