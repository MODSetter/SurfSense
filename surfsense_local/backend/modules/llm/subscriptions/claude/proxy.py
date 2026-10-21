"""The API's own proxy for Claude Code, on a port it picks itself.

Not Electron's, as opencode's is: the API starts every Claude Code run, so it
can hand each one the address. Every run's traffic goes through it, so egress
consent holds for a program SurfSense does not control.
"""

import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session, sessionmaker

from modules.agent.runtime_proxy.server import serving_runtime_proxy
from modules.llm.subscriptions.claude.proxy_hosts import DEFAULT_HOSTS, ClaudeHosts

_url: str | None = None


class ProxyNotServingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SurfSense's proxy for Claude Code is not running")


def claude_proxy_url() -> str | None:
    """Where Claude Code runs send their traffic; None outside a serving API."""
    return _url


def required_claude_proxy_url() -> str:
    """The proxy's address, or a refusal: Claude Code never runs around egress."""
    if _url is None:
        raise ProxyNotServingError
    return _url


@contextlib.asynccontextmanager
async def serving_claude_proxy(
    sessions: sessionmaker[Session],
    host: str,
    *,
    hosts: tuple[tuple[str, int], ...] = DEFAULT_HOSTS,
) -> AsyncIterator[int]:
    global _url
    async with serving_runtime_proxy(
        sessions,
        host,
        0,
        allowed=ClaudeHosts(sessions, hosts),
        client="Claude Code",
    ) as port:
        _url = f"http://{host}:{port}"
        try:
            yield port
        finally:
            _url = None
