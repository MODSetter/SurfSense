"""An agent run's Claude Code reaches Anthropic and the turn's ready plugins, and nothing else (ADR 0059)."""

import pytest
from sqlalchemy import Engine

from modules.agent.engines.claude_code import agent_proxy
from modules.agent.engines.claude_code.agent_proxy import AgentHosts
from modules.egress.service import set_enabled
from modules.llm.subscriptions.claude import proxy as claude_proxy
from shared.db import create_session_factory
from tests.integration.agent.test_plugin_proxy import Echo, connect_plugin, through

pytestmark = pytest.mark.integration


async def test_a_ready_plugins_host_is_tunnelled_to(engine: Engine, echo: Echo) -> None:
    """Claude Code connects to the plugin itself, as opencode does."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    async with agent_proxy.serving_agent_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        head, echoed = await through(
            port, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
        )

    assert head.startswith(b"HTTP/1.1 200")
    assert echoed == b"ping"


async def test_the_chat_proxy_still_refuses_a_plugins_host(
    engine: Engine,
    echo: Echo,
) -> None:
    """A chat run is given no plugin, so its proxy passes none."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    async with claude_proxy.serving_claude_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        head, _ = await through(
            port, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
        )

    assert head.startswith(b"HTTP/1.1 403")


def test_anthropics_hosts_follow_the_users_consent(engine: Engine) -> None:
    """The same consent as a chat run's: each host only while it is on."""
    hosts = AgentHosts(create_session_factory(engine))

    assert hosts.read() == frozenset()

    with create_session_factory(engine)() as session:
        set_enabled(session, "host:api.anthropic.com", True)
        session.commit()

    assert hosts.read() == {("api.anthropic.com", 443)}


async def test_runs_know_the_agent_proxys_address_only_while_it_serves(
    engine: Engine,
) -> None:
    """An agent run never starts around egress."""
    with pytest.raises(claude_proxy.ProxyNotServingError):
        agent_proxy.required_agent_proxy_url()

    async with agent_proxy.serving_agent_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        assert agent_proxy.required_agent_proxy_url() == f"http://127.0.0.1:{port}"

    with pytest.raises(claude_proxy.ProxyNotServingError):
        agent_proxy.required_agent_proxy_url()
