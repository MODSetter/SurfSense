"""On Stop, the plugin host is told to end the thread's calls, on whichever copy runs them."""

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from modules.agent.plugin_tools.thread_calls import CALLS_HEADER
from modules.agent.plugin_tools.turn_plugins import TurnPlugin

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5.0


async def stop_plugin_calls(plugins: list[TurnPlugin]) -> None:
    """Once per host and sign-in; a host that cannot be reached leaves its call to run out."""
    stops = {
        (_origin(plugin.url), plugin.headers.get("authorization", "")): plugin.headers
        for plugin in plugins
        if CALLS_HEADER in plugin.headers
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
        for (origin, _), headers in stops.items():
            try:
                await http.post(f"{origin}/cancel", headers=headers)
            except httpx.HTTPError:
                logger.warning("could not stop the plugin calls on %s", origin)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
