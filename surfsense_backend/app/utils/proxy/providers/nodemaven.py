"""NodeMaven residential / rotating proxy provider.

Takes the shared ``PROXY_URL`` env, like ``custom`` and ``dataimpulse``. What it
adds is NodeMaven's username syntax, ``<login>-<param>-<value>-...``:

* :meth:`get_location` reads the ``-country-<cc>`` parameter so the crawler's
  geoip-match can align the browser locale with the exit country.
* Country routing and sticky sessions rewrite the username with
  ``-country-<cc>`` and ``-sid-<id>``.

Rotation happens server-side (a fresh exit IP per connection without ``sid``),
so this is NOT :pyattr:`~ProxyProvider.is_pool_backed`.

Example URL::

    http://your_login-country-us:your_password@gate.nodemaven.com:8080

``region``, ``city`` and ``isp`` belong to a country, so they are dropped when
the country is changed and kept otherwise; ``ttl`` and other parameters are
kept as written.
"""

import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from app.config import Config
from app.utils.proxy.base import ProxyProvider

_COUNTRY_RE = re.compile(r"-country-([A-Za-z_]+)")
_LOCATION_RE = re.compile(r"-(?:country|region|city|isp)-[A-Za-z0-9_]+")
_SESSION_RE = re.compile(r"-sid-[A-Za-z0-9]+")


def _safe_session_id(session_id: str) -> str:
    # "-" separates parameters in the username, so a session id is alphanumeric.
    safe_id = re.sub(r"[^A-Za-z0-9]", "", session_id)
    if not safe_id:
        raise ValueError("session_id must contain at least one letter or digit")
    return safe_id


def _safe_country(country: str | None) -> str | None:
    if country is None:
        return None
    safe_country = re.sub(r"[^a-z]", "", country.lower())
    return safe_country or None


class NodeMavenProvider(ProxyProvider):
    """Provider for a NodeMaven proxy URL in the shared ``PROXY_URL`` env."""

    name = "nodemaven"

    def get_proxy_url(self) -> str | None:
        url = (Config.PROXY_URL or "").strip()
        return url or None

    def get_location(self) -> str:
        """Country from the ``-country-<cc>`` username parameter, or ``""``."""
        url = self.get_proxy_url()
        if not url:
            return ""
        match = _COUNTRY_RE.search(unquote(urlsplit(url).username or ""))
        return match.group(1).lower() if match else ""

    def _rewrite_proxy_url(
        self, *, country: str | None = None, session_id: str | None = None
    ) -> str | None:
        url = self.get_proxy_url()
        if not url:
            return None
        parts = urlsplit(url)
        username = _SESSION_RE.sub("", unquote(parts.username or ""))
        safe_country = _safe_country(country)
        if safe_country is not None and safe_country != self.get_location():
            username = _LOCATION_RE.sub("", username) + f"-country-{safe_country}"
        if session_id is not None:
            username += f"-sid-{_safe_session_id(session_id)}"
        userinfo = quote(username, safe="")
        if parts.password is not None:
            userinfo += f":{quote(unquote(parts.password), safe='')}"
        netloc = f"{userinfo}@{parts.hostname or ''}"
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit(
            (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
        )

    def get_geo_proxy_url(self, country: str | None = None) -> str | None:
        """Return the configured URL routed to ``country`` when one is given."""
        if not _safe_country(country):
            return self.get_proxy_url()
        return self._rewrite_proxy_url(country=country)

    def get_sticky_proxy_url(
        self, session_id: str, country: str | None = None
    ) -> str | None:
        """Return the configured URL with a session id and optional country."""
        return self._rewrite_proxy_url(country=country, session_id=session_id)
