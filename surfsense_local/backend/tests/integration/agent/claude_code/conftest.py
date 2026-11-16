"""A stand-in Claude Code for agent turns, and the fixtures shared with the Claude chat and proxy tests."""

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from modules.agent.engines import thread_engine
from modules.agent.engines.claude_code import turn as claude_turn
from modules.agent.engines.claude_code.engine import ClaudeCodeEngine
from modules.llm.subscriptions.claude import proxy as claude_proxy
from tests.claude_agent_stand_in import ScriptedAgentRun, Step
from tests.integration.llm.claude.conftest import (
    FakeClaude,
    claude_on_this_machine,
    fake_claude,
)
from tests.integration.llm.claude.test_claude_proxy import echo

__all__ = ["FakeClaude", "claude_on_this_machine", "echo", "fake_claude"]


class ClaudeAgent:
    """Every agent run the API starts, playing `turns` in order, one per message sent."""

    def __init__(self) -> None:
        self.turns: list[list[Step]] = []
        self.started: list[ScriptedAgentRun] = []
        # Each MCP server's settled status, by name; connected unless named.
        self.statuses: dict[str, str] = {}

    async def open(self, options: ClaudeAgentOptions) -> ScriptedAgentRun:
        run = ScriptedAgentRun(options, self.turns, self.statuses)
        self.started.append(run)
        return run


@pytest.fixture
def claude_agent(
    monkeypatch: pytest.MonkeyPatch, fake_claude: FakeClaude
) -> ClaudeAgent:
    """Stand in for the user's Claude Code in agent turns; nothing leaves the machine."""
    agent = ClaudeAgent()
    monkeypatch.setattr(claude_turn, "open_run", agent.open)
    # A serving API's proxy address; scripted runs never connect to it.
    monkeypatch.setattr(claude_proxy, "_url", "http://127.0.0.1:9")

    async def nothing_changed(*_args: object, **_kwargs: object) -> int:
        return 0

    # Checking plugins for changed tools reaches their servers.
    monkeypatch.setattr(claude_turn, "check_changed_tools", nothing_changed)
    # Fresh per test: its skills and config files live in this test's data folder.
    monkeypatch.setattr(thread_engine, "_CLAUDE_CODE", ClaudeCodeEngine())
    return agent
