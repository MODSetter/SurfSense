"""An Agentic thread answered by the developer's own Claude Code, through the app's API."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from httpx import AsyncClient
from mcp.server.mcpserver import MCPServer
from sqlalchemy import Engine

from modules.agent.engines.claude_code.agent_proxy import serving_agent_proxy
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


async def test_an_agentic_turn_reads_a_large_plugin_result_claude_code_saved(
    client: AsyncClient, engine: Engine, claude_binary: Path, ledger_plugin: str
) -> None:
    """The plugin answers, Claude Code saves its long result, and the model reads it
    there, with no plugin named unreachable and no read refused."""
    _connect(engine, ledger_plugin)
    sessions = create_session_factory(engine)
    async with (
        serving_claude_proxy(sessions, "127.0.0.1"),
        serving_agent_proxy(sessions, "127.0.0.1"),
    ):
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
            frames = await _send(
                client,
                opened.json()["id"],
                "Call the ledger plugin's long_page tool once. Its output ends with a "
                "line that starts with MARKER-. Find that line in the full output and "
                "reply with it alone.",
            )
        finally:
            await close_engines()

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
