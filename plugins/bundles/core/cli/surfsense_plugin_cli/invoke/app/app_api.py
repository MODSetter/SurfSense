"""What invoke reads from the running app before the plugin starts."""

import json
import urllib.error
import urllib.request

# Loopback: a proxy would only get in the way.
_opener_without_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def answers(url: str) -> bool:
    """Whether the app is up: its /health answers once it can take requests."""
    try:
        with _opener_without_proxy.open(f"{url}/health", timeout=3) as reply:
            return reply.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def read_from_app(url: str, path: str) -> object:
    """One of the app's routes, as JSON."""
    with _opener_without_proxy.open(f"{url}{path}", timeout=30) as reply:
        return json.loads(reply.read())
