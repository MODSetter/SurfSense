"""What the Claude agent engine relies on, checked against the installed Claude Code.

Claude Code updates itself, so each behaviour the engine assumes is a test here
(docs/architecture/claude-plan.md, Tests).
"""

import asyncio
import json
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from claude_agent_sdk import (
    AssistantMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from mcp.server.mcpserver import MCPServer

from modules.agent.engines.claude_code.agent_options import AgentLaunch, agent_options
from modules.agent.engines.claude_code.approvals import Approvals
from modules.agent.engines.claude_code.gate import Gate
from modules.agent.engines.claude_code.mcp_config import write_mcp_config
from modules.agent.engines.claude_code.plugin_statuses import unavailable_plugins
from modules.agent.engines.claude_code.saved_results import claude_home
from modules.agent.engines.claude_code.skills_plugin import build_skills_plugin
from modules.agent.engines.claude_code.turn_link import TurnLink
from modules.agent.opencode_config import skills_folder
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.llm.subscriptions.claude.run import open_run
from tests.claude_code.connect_recorder import recording_proxy

pytestmark = pytest.mark.claude_code
SECRET = "plugin-sign-in-7731"
# Past the size Claude Code gives the model whole; it saved an 80.7 KB result to a file.
LONG_RESULT_CHARS = 120_000
MARKER = "MARKER-4417"


@pytest.fixture(scope="module")
def notes_server() -> Iterator[str]:
    """A plugin-like MCP server on loopback, which Claude Code reaches around the proxy."""
    server = MCPServer("notes")

    @server.tool()
    def save_note(text: str) -> str:
        """Save a note."""
        return f"saved {text}"

    @server.tool()
    def long_page() -> str:
        """Return one long page of the ledger."""
        return "ledger line\n" * (LONG_RESULT_CHARS // 12) + MARKER

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


def _setup(
    binary: Path,
    tmp_path: Path,
    proxy_url: str,
    servers: dict[str, Any],
    *,
    rules: dict[str, str] | None = None,
    hidden: list[str] | None = None,
) -> tuple[AgentLaunch, Approvals, asyncio.Queue]:
    folder = tmp_path / "thread"
    (folder / "outputs").mkdir(parents=True)
    (folder / "sources").mkdir()
    skills = build_skills_plugin(skills_folder(), tmp_path / "skills-plugin")
    approvals = Approvals()
    link = TurnLink(7, approvals)
    events: asyncio.Queue = asyncio.Queue()
    session_id = str(uuid.uuid4())
    gate = Gate(
        folder,
        skills.skills,
        skills.names,
        rules or {},
        claude_home=claude_home(),
        session_id=session_id,
    )
    link.begin(gate, events, session_id)
    launch = AgentLaunch(
        binary=binary,
        proxy_url=proxy_url,
        folder=folder,
        model="haiku",
        session_id=session_id,
        resumed=False,
        mcp_file=write_mcp_config(tmp_path / "mcp", servers),
        disallowed=hidden or [],
        skills=skills,
        link=link,
        store=None,
        thinking=False,
    )
    return launch, approvals, events


async def _turn(launch: AgentLaunch, prompt: str) -> list[Any]:
    run = await open_run(agent_options(launch))
    try:
        return [message async for message in run.send(prompt)]
    finally:
        await run.close()


def _results(messages: list[Any]) -> dict[str, ToolResultBlock]:
    """Each call's result, by the tool it called."""
    names = {
        block.id: block.name
        for message in messages
        if isinstance(message, AssistantMessage)
        for block in message.content
        if isinstance(block, ToolUseBlock)
    }
    return {
        names[block.tool_use_id]: block
        for message in messages
        if isinstance(message, UserMessage) and isinstance(message.content, list)
        for block in message.content
        if isinstance(block, ToolResultBlock) and block.tool_use_id in names
    }


async def test_the_gate_decides_each_call_in_default_mode(
    claude_binary: Path, tmp_path: Path
) -> None:
    """A write under outputs/ runs; a read outside the thread is refused with the gate's reason."""
    async with recording_proxy() as proxy:
        launch, _, _ = _setup(claude_binary, tmp_path, proxy.url, {})
        messages = await _turn(
            launch,
            "Do two things with your tools, then reply OK: write the text 'ok' to "
            "outputs/done.md, and read the file /etc/hosts.",
        )

    assert (launch.folder / "outputs" / "done.md").read_text().strip() == "ok"
    refused = _results(messages)["Read"]
    assert refused.is_error
    assert "thread's folder" in str(refused.content)


async def test_the_launch_hides_tools_keeps_headers_off_the_command_line_and_uses_the_proxy(
    claude_binary: Path, tmp_path: Path, notes_server: str
) -> None:
    """A denied tool is never offered; a remote plugin is reached through the proxy only."""
    servers = {
        "notes": {"type": "http", "url": notes_server},
        "remote": {
            "type": "http",
            "url": "https://plugin.example.com/mcp",
            "headers": {"Authorization": f"Bearer {SECRET}"},
        },
    }
    async with recording_proxy() as proxy:
        launch, _, _ = _setup(
            claude_binary,
            tmp_path,
            proxy.url,
            servers,
            hidden=["mcp__notes__long_page"],
        )
        run = await open_run(agent_options(launch))
        try:
            processes = subprocess.run(
                ["ps", "-axww", "-o", "args="],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            messages = [m async for m in run.send("Reply OK.")]
        finally:
            await run.close()

    init = next(
        m for m in messages if isinstance(m, SystemMessage) and m.subtype == "init"
    )
    assert "mcp__notes__save_note" in init.data["tools"]
    assert "mcp__notes__long_page" not in init.data["tools"]
    assert "surfsense:surfsense-documents" in init.data["skills"]
    assert SECRET not in processes
    assert ("plugin.example.com:443", False) in proxy.connects


async def test_the_model_reads_a_long_result_claude_code_saved_for_it(
    claude_binary: Path, tmp_path: Path, notes_server: str
) -> None:
    """Too large to give whole, it is saved under the session; the gate lets the model read it."""
    async with recording_proxy() as proxy:
        launch, _, _ = _setup(
            claude_binary,
            tmp_path,
            proxy.url,
            {"notes": {"type": "http", "url": notes_server}},
            rules={"mcp__notes__long_page": "allow"},
        )
        messages = await _turn(
            launch,
            "Call long_page once. Its output ends with a line that starts with "
            "MARKER-. Find that line in the full output and reply with it alone.",
        )

    results = _results(messages)
    assert "Full output saved to" in json.dumps(
        results["mcp__notes__long_page"].content
    )
    reads = [results[tool] for tool in ("Read", "Grep") if tool in results]
    assert reads
    assert not any(result.is_error for result in reads)
    replies = [
        block.text
        for message in messages
        if isinstance(message, AssistantMessage)
        for block in message.content
        if hasattr(block, "text")
    ]
    assert MARKER in " ".join(replies)


async def test_an_approval_can_wait_longer_than_a_hooks_timeout(
    claude_binary: Path, tmp_path: Path, notes_server: str
) -> None:
    """The hook answers `ask` at once; can_use_tool waits for the user past 60 s."""
    async with recording_proxy() as proxy:
        launch, approvals, events = _setup(
            claude_binary,
            tmp_path,
            proxy.url,
            {"notes": {"type": "http", "url": notes_server}},
            rules={"mcp__notes__save_note": "ask"},
        )

        async def answer_late() -> None:
            asked = await events.get()
            await asyncio.sleep(65)
            approvals.answer(7, asked.properties["id"], "once")

        answering = asyncio.create_task(answer_late())
        messages = await _turn(
            launch, "Call save_note with the text 'q3' once, then reply OK."
        )
        await answering

    saved = _results(messages)["mcp__notes__save_note"]
    assert not saved.is_error
    assert "saved q3" in json.dumps(saved.content)


async def test_after_an_interrupt_the_same_claude_code_answers_the_next_message(
    claude_binary: Path, tmp_path: Path
) -> None:
    """Read to its result, the interrupted turn leaves nothing for the next one to read."""
    async with recording_proxy() as proxy:
        launch, _, _ = _setup(claude_binary, tmp_path, proxy.url, {})
        run = await open_run(agent_options(launch))
        try:
            first = []
            async for message in run.send("Write a 600-word essay about rivers."):
                first.append(message)
                if isinstance(message, AssistantMessage) and len(first) > 2:
                    await run.interrupt()
            second = [m async for m in run.send("Reply with exactly: AGAIN")]
        finally:
            await run.close()

    assert "AGAIN" in json.dumps(
        [
            b.text
            for m in second
            if isinstance(m, AssistantMessage)
            for b in m.content
            if hasattr(b, "text")
        ]
    )


@pytest.fixture(scope="module")
def slow_server() -> Iterator[str]:
    """A plugin a few seconds away, as a remote one is: each request takes 1.5 s."""
    server = MCPServer("slow")

    @server.tool()
    def ping() -> str:
        """Answer pong."""
        return "pong"

    app = server.streamable_http_app(stateless_http=True, json_response=True)

    async def slow(scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            await asyncio.sleep(1.5)
        await app(scope, receive, send)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    runner = uvicorn.Server(
        uvicorn.Config(slow, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=runner.run, daemon=True).start()
    while not runner.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    runner.should_exit = True


async def test_a_plugin_slow_to_connect_is_settled_in_the_turns_init(
    claude_binary: Path, tmp_path: Path, slow_server: str
) -> None:
    """Claude Code holds a turn's init until its plugins connect; the engine reads them there."""
    async with recording_proxy() as proxy:
        launch, _, _ = _setup(
            claude_binary,
            tmp_path,
            proxy.url,
            {"slow": {"type": "http", "url": slow_server}},
            rules={"mcp__slow__ping": "allow"},
        )
        messages = await _turn(launch, "Reply OK.")

    init = next(
        m for m in messages if isinstance(m, SystemMessage) and m.subtype == "init"
    )
    plugin = TurnPlugin(name="slow", title="Slow", url=slow_server, headers={})
    assert unavailable_plugins(init.data["mcp_servers"], [plugin]) == []
    assert "mcp__slow__ping" in init.data["tools"]
