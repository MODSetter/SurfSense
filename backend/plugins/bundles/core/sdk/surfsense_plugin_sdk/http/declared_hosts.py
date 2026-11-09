"""Keeps a plugin's HTTP to the hosts its manifest declares, on every hop.

A check, not enforcement: a plugin that opens its own socket is not checked.
"""

import urllib.parse

from surfsense_plugin_sdk.run.current_run import current_run


class HostNotDeclared(Exception):
    """A request to a host manifest.json does not list, refused before connecting."""

    def __init__(self, host: str) -> None:
        super().__init__(
            f'"{host}" is not in "hosts" in manifest.json, so the plugin may not'
            " reach it"
        )
        self.host = host


def checked_host(url: str) -> str:
    """The host a URL reaches, once it is a web address and declared."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"http fetches http and https only, not {parts.scheme}: URLs")
    host = parts.hostname or ""
    if host not in current_run().manifest["hosts"]:
        raise HostNotDeclared(host)
    return host
