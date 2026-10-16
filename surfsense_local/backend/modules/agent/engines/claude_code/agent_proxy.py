"""The proxy an agent run's Claude Code goes through: Anthropic's hosts and the ready plugins' (ADR 0059).

Separate from a chat run's, which passes Anthropic's hosts alone, so a chat run
can never reach a plugin. Both checks are the ones already in use, not copies.
"""

import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session, sessionmaker

from modules.agent.plugin_proxy.allowed_hosts import AllowedHosts
from modules.agent.plugin_proxy.server import serving_plugin_proxy
from modules.llm.subscriptions.claude.proxy import ProxyNotServingError
from modules.llm.subscriptions.claude.proxy_hosts import DEFAULT_HOSTS, ClaudeHosts

_url: str | None = None


class AgentHosts(ClaudeHosts):
    def _ready(self, session: Session) -> frozenset[tuple[str, int]]:
        return ClaudeHosts._ready(self, session) | AllowedHosts._ready(self, session)


def required_agent_proxy_url() -> str:
    """The proxy's address, or a refusal: Claude Code never runs around egress."""
    if _url is None:
        raise ProxyNotServingError
    return _url


@contextlib.asynccontextmanager
async def serving_agent_proxy(
    sessions: sessionmaker[Session],
    host: str,
    *,
    hosts: tuple[tuple[str, int], ...] = DEFAULT_HOSTS,
) -> AsyncIterator[int]:
    global _url
    async with serving_plugin_proxy(
        sessions,
        host,
        0,
        allowed=AgentHosts(sessions, hosts),
        client="Claude Code",
    ) as port:
        _url = f"http://{host}:{port}"
        try:
            yield port
        finally:
            _url = None
