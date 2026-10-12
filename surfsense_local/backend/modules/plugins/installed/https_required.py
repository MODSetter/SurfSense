"""A remote plugin's server is reached over HTTPS: the agent's only way out is a TLS tunnel."""

from urllib.parse import urlsplit

from modules.egress.service import host_destination


def needs_https(url: str) -> bool:
    """True for a server off this computer that is not on HTTPS."""
    return host_destination(url) is not None and urlsplit(url).scheme != "https"
