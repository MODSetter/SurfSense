"""SurfSense's plugin host, compiled in: the one place the license key is ever sent."""

from urllib.parse import urlsplit, urlunsplit

from shared.config import get_plugin_host_settings

PLUGIN_HOST = "https://plugins.surfsense.com"


def plugin_host() -> str:
    """The compiled host, or the local one a developer's build points at instead."""
    return get_plugin_host_settings().plugin_host_url or PLUGIN_HOST


def on_plugin_host(url: str) -> bool:
    return _origin(url) == _origin(plugin_host())


def as_served(url: str) -> str:
    """A listed URL on the compiled host, moved to the host this build reaches."""
    if _origin(url) != _origin(PLUGIN_HOST):
        return url
    served = urlsplit(plugin_host())
    return urlunsplit(
        urlsplit(url)._replace(scheme=served.scheme, netloc=served.netloc)
    )


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc
