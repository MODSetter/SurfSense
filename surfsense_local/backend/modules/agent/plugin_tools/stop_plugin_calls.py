"""On Stop, or when opencode gives up on a call, the plugin host is told to end the thread's calls, on whichever copy runs them."""

import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from modules.agent.plugin_tools.thread_calls import CALLS_HEADER
from modules.agent.plugin_tools.turn_plugins import TurnPlugin

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5.0
# The MCP code opencode's client gives a call it ended for lasting too long without
# progress; a plugin's own error that mentions a timeout is not one.
_TIMED_OUT = "mcp error -32001"
_RUNNING = ("pending", "running")

_stopping: set[asyncio.Task[None]] = set()


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


def timed_out_plugin(frame: dict, plugins: list[TurnPlugin]) -> TurnPlugin | None:
    """The plugin on SurfSense's plugin host whose call opencode gave up on, if the step frame says so.

    The host never hears opencode's own cancel, so it would run the call to its end.
    """
    error = str(frame.get("error") or "").lower()
    if (
        frame.get("type") != "agent-step"
        or frame.get("status") != "error"
        or _TIMED_OUT not in error
    ):
        return None
    return _on_host(frame, plugins)


class HostCalls:
    """A turn's calls on SurfSense's plugin host still running, and the cancels waiting on them.

    The host ends every call of the thread under one sign-in at once, so a call
    opencode gave up on is ended there only once no other call of the turn runs.
    """

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._waiting: list[TurnPlugin] = []

    def follow(self, frame: dict, plugins: list[TurnPlugin]) -> None:
        """Note a step frame of the turn; send the cancels waiting once none runs."""
        if frame.get("type") != "agent-step" or _on_host(frame, plugins) is None:
            return
        if frame.get("status") in _RUNNING:
            self._running.add(frame["id"])
            return
        self._running.discard(frame["id"])
        if (late := timed_out_plugin(frame, plugins)) is not None:
            self._waiting.append(late)
        if not self._running:
            self.end()

    def end(self) -> None:
        """Send the cancels still waiting; at the turn's end, whatever the frames last said."""
        if self._waiting:
            stop_soon(self._waiting)
            self._waiting = []


def _on_host(frame: dict, plugins: list[TurnPlugin]) -> TurnPlugin | None:
    return next(
        (
            plugin
            for plugin in plugins
            if CALLS_HEADER in plugin.headers and frame.get("tool") in plugin.rules
        ),
        None,
    )


def stop_soon(plugins: list[TurnPlugin]) -> None:
    """`stop_plugin_calls` in the background, so the turn's frames do not wait on the host."""
    task = asyncio.create_task(stop_plugin_calls(plugins))
    _stopping.add(task)
    task.add_done_callback(_stopping.discard)
