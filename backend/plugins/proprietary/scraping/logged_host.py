"""A scraped address as a log line may show it: the host, never what was asked there.

Plugin records are kept for rate limits, abuse and billing; the path or query of a
page a user asked for is none of those.
"""

from urllib.parse import urlsplit


def logged_host(url: str | None) -> str:
    try:
        return (urlsplit(url).hostname or "-") if url else "-"
    except ValueError:
        return "-"
