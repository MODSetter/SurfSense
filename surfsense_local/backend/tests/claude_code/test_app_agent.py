"""An Agentic thread answered by the developer's own Claude Code, through the app's API."""

import asyncio
import json
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn
from httpx import AsyncClient
from mcp.server.mcpserver import MCPServer
from sqlalchemy import Engine

from api.config import get_settings
from api.main import create_app
from modules.agent.engines.thread_engine import close_engines
from modules.llm.subscriptions.claude.proxy import serving_claude_proxy
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.models import ToolApproval
from modules.plugins.installed.third_party import set_third_party_on
from modules.plugins.installed.tool_settings import set_tool
from shared.db import create_session_factory

pytestmark = pytest.mark.claude_code
HAIKU = "claude-haiku-5-5"
# Past the size Claude Code gives the model whole: it is saved, and the end is only there.
MARKER = "MARKER-8812"
LONG_PAGE = "ledger line\n" * 10_000 + MARKER


@pytest.fixture
def ledger_plugin() -> Iterator[str]:
    """A plugin on this computer whose one tool returns about 120 KB."""
    server = MCPServer("ledger")

    @server.tool()
    def long_page() -> str:
        """Return the whole ledger."""
        return LONG_PAGE

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    runner = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=runner.run, daemon=True).start()
    while not runner.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    runner.should_exit = True


@pytest_asyncio.fixture(loop_scope="function")
async def served_client(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """The app on a real port, as Electron runs it: Claude Code reaches its plugins through
    the gateway there. Served on the test's own loop, where its Claude Code is closed."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setattr(get_settings(), "port", port)
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    runner = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
        )
    )
    serving = asyncio.create_task(runner.serve())
    while not runner.started:
        await asyncio.sleep(0.05)
    try:
        async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            yield client
    finally:
        runner.should_exit = True
        await serving


def _connect(engine: Engine, url: str) -> None:
    """Connected and ready, its tool read-only and allowed without asking."""
    long_page = SourceTool(
        name="long_page",
        title=None,
        description="Return the whole ledger.",
        input_schema={"type": "object", "properties": {}},
        annotations={"readOnlyHint": True},
    )
    with create_session_factory(engine)() as session:
        store_custom_plugin(session, "ledger", "Ledger", url, None, [long_page])
        set_third_party_on(session, True)
        set_tool(
            session, "ledger", "long_page", enabled=True, approval=ToolApproval.ALWAYS
        )
        session.commit()


async def _send(client: AsyncClient, thread_id: int, text: str) -> list[dict]:
    frames: list[dict] = []
    async with client.stream(
        "POST",
        f"/chat/threads/{thread_id}/messages",
        json={"text": text},
        timeout=300,
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                frames.append(json.loads(line[len("data: ") :]))
    return frames


async def _claude_turn(client: AsyncClient, engine: Engine, text: str) -> list[dict]:
    """One Agentic turn on a Claude plan model, its hosts allowed, through the app."""
    sessions = create_session_factory(engine)
    async with serving_claude_proxy(sessions, "127.0.0.1"):
        await client.put(
            "/egress",
            json={
                "destinations": ["host:api.anthropic.com", "host:platform.claude.com"],
                "enabled": True,
            },
        )
        connection = (
            await client.post("/llm/connections/claude", json={"label": "Claude"})
        ).json()
        chosen = await client.put(
            "/llm/selection/text_gen",
            json={
                "provider": "openai_compatible",
                "connection_id": connection["id"],
                "name": HAIKU,
            },
        )
        assert chosen.status_code == 200, chosen.text
        workspace = (await client.post("/workspaces", json={"name": "w"})).json()
        opened = await client.post(
            f"/workspaces/{workspace['id']}/chat/threads", json={"mode": "agentic"}
        )
        assert opened.status_code == 201, opened.text
        try:
            return await _send(client, opened.json()["id"], text)
        finally:
            await close_engines()


async def test_an_agentic_turn_reads_a_large_plugin_result_claude_code_saved(
    served_client: AsyncClient, engine: Engine, claude_binary: Path, ledger_plugin: str
) -> None:
    """The plugin answers, Claude Code saves its long result, and the model reads it
    there, with no plugin named unreachable and no read refused."""
    _connect(engine, ledger_plugin)

    frames = await _claude_turn(
        served_client,
        engine,
        "Call the ledger plugin's long_page tool once. Its output ends with a "
        "line that starts with MARKER-. Find that line in the full output and "
        "reply with it alone.",
    )

    assert not [f for f in frames if f["type"] == "error"], frames
    assert not [f for f in frames if f["type"] == "agent-plugins-unavailable"]
    steps = {
        f["tool"]: f
        for f in frames
        if f["type"] == "agent-step" and f["status"] in {"completed", "error"}
    }
    assert steps["ledger_long_page"]["status"] == "completed"
    assert "Full output saved to" in steps["ledger_long_page"]["output"]
    reads = [steps[tool] for tool in ("read", "grep") if tool in steps]
    assert reads, steps
    assert all(step["status"] == "completed" for step in reads), reads
    assert any(
        "/tool-results/"
        in str(step["input"].get("filePath") or step["input"].get("path"))
        for step in reads
    ), reads
    completed = next(f for f in frames if f["type"] == "completed")
    assert MARKER in completed["text"]


FOUND = "FOUND-4471"


@pytest.fixture
def catalog_plugin() -> Iterator[str]:
    """A plugin whose tools' definitions pass a tenth of the window, so Claude Code
    defers them, with one tool the turn needs among them."""
    server = MCPServer("catalog")
    padding = " It belongs to the warehouse catalog and lists stock by aisle." * 20

    def make(n: int):
        def tool() -> str:
            return f"aisle {n}"

        tool.__doc__ = f"Report the stock of aisle {n}.{padding}"
        return tool

    for n in range(80):
        server.tool(name=f"aisle_{n}")(make(n))

    @server.tool()
    def find_marker() -> str:
        """Return the marker the user asks for."""
        return FOUND

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    runner = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=runner.run, daemon=True).start()
    while not runner.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    runner.should_exit = True


async def test_claude_code_finds_a_deferred_plugin_tool_by_search(
    served_client: AsyncClient, engine: Engine, claude_binary: Path, catalog_plugin: str
) -> None:
    """Past a tenth of the window its tools are deferred; the turn still finds and calls one."""
    tools = [
        SourceTool(
            name=name,
            title=None,
            description="Catalog tool.",
            input_schema={"type": "object", "properties": {}},
            annotations={"readOnlyHint": True},
        )
        for name in [*(f"aisle_{n}" for n in range(80)), "find_marker"]
    ]
    with create_session_factory(engine)() as session:
        store_custom_plugin(session, "catalog", "Catalog", catalog_plugin, None, tools)
        set_third_party_on(session, True)
        for tool in tools:
            set_tool(
                session,
                "catalog",
                tool.name,
                enabled=True,
                approval=ToolApproval.ALWAYS,
            )
        session.commit()

    frames = await _claude_turn(
        served_client,
        engine,
        "Use the catalog plugin's find_marker tool and reply with exactly what it returns.",
    )

    steps = [f for f in frames if f["type"] == "agent-step"]
    assert not [f for f in frames if f["type"] == "error"], frames
    called = [f for f in steps if f["tool"] == "catalog_find_marker"]
    assert called and called[-1]["status"] == "completed", steps
    reply = "".join(f.get("text", "") for f in frames if f["type"] == "delta")
    assert FOUND in reply
