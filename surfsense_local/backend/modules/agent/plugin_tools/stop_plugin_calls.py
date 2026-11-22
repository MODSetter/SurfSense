"""On Stop, the plugin host is told to end the thread's calls, on whichever copy runs them.

A call a runtime gave up on alone is ended by the gateway, which sees its cancel
(plugin_gateway/host_calls.py).
"""

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
        (origin(server.url), server.headers.get("authorization", "")): server.headers
        for server in (plugin.upstream for plugin in plugins if plugin.on_plugin_host)
        if server is not None and CALLS_HEADER in server.headers
    }
    for (host, _), headers in stops.items():
        await stop_host_calls(host, headers)


async def stop_host_calls(host: str, headers: dict[str, str]) -> None:
    """End every call of the thread the headers name, on the host at `host`."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
        try:
            await http.post(f"{host}/cancel", headers=headers)
        except httpx.HTTPError:
            logger.warning("could not stop the plugin calls on %s", host)


def origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
