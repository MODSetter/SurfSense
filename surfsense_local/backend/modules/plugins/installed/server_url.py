"""One spelling per server, so the same server is never connected twice.

Scheme and host are case-insensitive, a default port and a trailing slash name nothing,
and a fragment never reaches the server. The path and the query can name a different
endpoint on one host, so they are kept as written.
"""

from urllib.parse import urlsplit, urlunsplit

DEFAULT_PORTS = {"http": 80, "https": 443}


def server_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    netloc = (
        host
        if parts.port in (None, DEFAULT_PORTS.get(scheme))
        else f"{host}:{parts.port}"
    )
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))
