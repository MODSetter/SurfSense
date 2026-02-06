"""
Residential proxy configuration utility.

Reads proxy credentials from the application Config and provides helper
functions that return proxy configs in the format expected by different
HTTP libraries (requests, httpx, aiohttp, Playwright).
"""

import base64
import json
import logging

from app.config import Config

logger = logging.getLogger(__name__)


def _build_password_b64() -> str | None:
    """
    Build the base64-encoded password dict required by anonymous-proxies.net.

    Returns ``None`` when the required config values are not set.
    """
    password = Config.RESIDENTIAL_PROXY_PASSWORD
    if not password:
        return None

    password_dict = {
        "p": password,
        "l": Config.RESIDENTIAL_PROXY_LOCATION,
        "t": Config.RESIDENTIAL_PROXY_TYPE,
    }
    return base64.b64encode(json.dumps(password_dict).encode("utf-8")).decode("utf-8")


def get_residential_proxy_url() -> str | None:
    """
    Return the fully-formed residential proxy URL, or ``None`` when not
    configured.

    The URL format is::

        http://<username>:<base64_password>@<hostname>/
    """
    username = Config.RESIDENTIAL_PROXY_USERNAME
    hostname = Config.RESIDENTIAL_PROXY_HOSTNAME
    password_b64 = _build_password_b64()

    if not all([username, hostname, password_b64]):
        return None

    return f"http://{username}:{password_b64}@{hostname}/"


def get_requests_proxies() -> dict[str, str] | None:
    """
    Return a ``{"http": …, "https": …}`` dict suitable for
    ``requests.Session.proxies`` and ``aiohttp`` ``proxy=`` kwarg,
    or ``None`` when not configured.
    """
    proxy_url = get_residential_proxy_url()
    if proxy_url is None:
        return None
    return {"http": proxy_url, "https": proxy_url}


def get_playwright_proxy() -> dict[str, str] | None:
    """
    Return a Playwright-compatible proxy dict::

        {"server": "http://host:port", "username": "…", "password": "…"}

    or ``None`` when not configured.
    """
    username = Config.RESIDENTIAL_PROXY_USERNAME
    hostname = Config.RESIDENTIAL_PROXY_HOSTNAME
    password_b64 = _build_password_b64()

    if not all([username, hostname, password_b64]):
        return None

    return {
        "server": f"http://{hostname}",
        "username": username,
        "password": password_b64,
    }
