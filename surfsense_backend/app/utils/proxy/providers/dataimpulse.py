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

ponytail: sticky sessions (a stable exit IP across requests) are another
username suffix (``__sid.<id>``) — the lever the Reddit scraper's README flags as
a TODO for its ``loid``-per-IP flow. Not built yet: Reddit isn't wired to a
route, so there's no caller to thread a session id through. Add a
``get_sticky_proxy_url(session_id)`` here (rewriting the username) when it lands.
"""

import logging
from urllib.parse import urlsplit

from app.config import Config
from app.utils.proxy.base import ProxyProvider

logger = logging.getLogger(__name__)

# DataImpulse encodes country routing as a "__cr.<country>" username suffix; the
# country token runs until the next "__" param (e.g. "__sid") or the end.
_COUNTRY_MARKER = "__cr."


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
