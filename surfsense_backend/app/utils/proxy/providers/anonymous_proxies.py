"""anonymous-proxies.net residential / rotating proxy provider.

The vendor (``rotating.dnsproxifier.com``) encodes the location and rotation
``type`` options inside a base64-encoded JSON "password". The hostname already
includes the port (e.g. ``rotating.dnsproxifier.com:31230``).
"""

import base64
import json
import logging

from app.config import Config
from app.utils.proxy.base import ProxyProvider

logger = logging.getLogger(__name__)


class AnonymousProxiesProvider(ProxyProvider):
    """Provider for anonymous-proxies.net credentials in ``RESIDENTIAL_PROXY_*``."""

    name = "anonymous_proxies"

    def _password_b64(self) -> str | None:
        """Build the base64-encoded password dict required by the vendor.

        Returns ``None`` when the password is not configured.
        """
        password = Config.RESIDENTIAL_PROXY_PASSWORD
        if not password:
            return None

        password_dict = {
            "p": password,
            "l": Config.RESIDENTIAL_PROXY_LOCATION,
            "t": Config.RESIDENTIAL_PROXY_TYPE,
        }
        return base64.b64encode(json.dumps(password_dict).encode("utf-8")).decode(
            "utf-8"
        )

    def get_proxy_url(self) -> str | None:
        username = Config.RESIDENTIAL_PROXY_USERNAME
        hostname = Config.RESIDENTIAL_PROXY_HOSTNAME
        password_b64 = self._password_b64()

        if not all([username, hostname, password_b64]):
            return None

        # No trailing slash: curl_cffi (Scrapling static fetcher) expects a bare
        # ``http://user:pass@host:port`` URL.
        return f"http://{username}:{password_b64}@{hostname}"

    def get_playwright_proxy(self) -> dict[str, str] | None:
        username = Config.RESIDENTIAL_PROXY_USERNAME
        hostname = Config.RESIDENTIAL_PROXY_HOSTNAME
        password_b64 = self._password_b64()

        if not all([username, hostname, password_b64]):
            return None

        return {
            "server": f"http://{hostname}",
            "username": username,
            "password": password_b64,
        }
