"""Addresses a stranger names for the runner to fetch: https on a public host only.

A name resolving to a private address still gets through; a GitHub-hosted runner has no
private network worth reaching, and the app's own egress rules apply once listed.
"""

import ipaddress
from urllib.parse import urlsplit


def address_problem(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return "must be an https link"
    host = parts.hostname
    if host == "localhost" or host.endswith(".localhost"):
        return "must be on a public host"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    return None if address.is_global else "must be on a public host"
