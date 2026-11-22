"""A call a runtime gave up on, ended on SurfSense's plugin host.

opencode and Claude Code send `notifications/cancelled` when a call is stopped
or runs past its limit, and leave its stream open. The host keeps no MCP
session to hear it, so the gateway asks the host to end the thread's calls; the
host ends every one under that sign-in at once, so it waits until no call of the
thread there is still wanted.
"""

import asyncio
import json
from typing import Any

from modules.agent.plugin_tools.stop_plugin_calls import stop_host_calls

# Where a thread's calls on the host go: its origin, the sign-in, the thread's token.
Host = tuple[str, ...]

_stopping: set[asyncio.Task[None]] = set()


class HostCalls:
    """Each thread's calls on the plugin host the gateway is forwarding, by request id."""

    def __init__(self) -> None:
        self._running: dict[Host, set[Any]] = {}
        self._given_up: dict[Host, set[Any]] = {}
        self._headers: dict[Host, dict[str, str]] = {}

    def sent(self, host: Host, body: bytes, headers: dict[str, str]) -> Any:
        """Note a message on its way to the host; the id of a call that began, else None."""
        for message in _messages(body):
            if message.get("method") == "tools/call" and "id" in message:
                self._running.setdefault(host, set()).add(message["id"])
                self._headers[host] = headers
                return message["id"]
            if message.get("method") == "notifications/cancelled":
                wanted = (message.get("params") or {}).get("requestId")
                if wanted in self._running.get(host, set()):
                    self._given_up.setdefault(host, set()).add(wanted)
                    self._settle(host)
        return None

    def answered(self, host: Host, request_id: Any) -> None:
        """A call's answer has ended, given up on or not."""
        self._running.get(host, set()).discard(request_id)
        given_up = self._given_up.get(host, set())
        if request_id in given_up:
            given_up.discard(request_id)
            return
        self._settle(host)

    def _settle(self, host: Host) -> None:
        """Stop the host's calls once every one still running was given up on."""
        given_up = self._given_up.get(host, set())
        running = self._running.get(host, set())
        if given_up and running <= given_up:
            stop_soon(host, self._headers.get(host, {}))
            given_up.clear()


def _messages(body: bytes) -> list[dict[str, Any]]:
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return []
    messages = message if isinstance(message, list) else [message]
    return [m for m in messages if isinstance(m, dict)]


def stop_soon(host: Host, headers: dict[str, str]) -> None:
    """In the background, so the runtime's cancel is answered at once."""
    task = asyncio.create_task(stop_host_calls(host[0], headers))
    _stopping.add(task)
    task.add_done_callback(_stopping.discard)


# One for the API process: a thread's calls may come on several requests at once.
HOST_CALLS = HostCalls()
