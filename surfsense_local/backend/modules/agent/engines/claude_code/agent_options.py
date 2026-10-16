"""What an agent run's Claude Code starts with (docs/architecture/claude-plan.md, A turn)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from modules.agent.engines.claude_code.skills_plugin import SkillsPlugin
from modules.agent.engines.claude_code.tool_names import for_claude
from modules.agent.engines.claude_code.turn_link import TurnLink
from modules.agent.opencode_config import agent_prompt
from modules.agent.plugin_tools.connect_limit import CONNECT_SECONDS
from modules.llm.subscriptions.claude.launch import launch_options

# opencode's tools in Claude Code's names: no Bash (ADR 0039), web, subagents or notebooks.
TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Skill"]
# Over Claude Code's 25,000, a result is refused as too large. One larger than
# Claude Code gives whole (an 80.7 KB one was) is still saved under the session,
# which the gate lets the model read, as opencode's tool-output folder.
MAX_RESULT_TOKENS = 100_000
# A scrape on SurfSense's plugin host can run minutes; opencode allows it 300 s.
TOOL_CALL_MS = 300_000
# The hook only decides, so this never runs out; an approval waits in can_use_tool.
HOOK_SECONDS = 30


@dataclass(frozen=True)
class AgentLaunch:
    binary: Path
    proxy_url: str
    folder: Path
    model: str
    session_id: str
    # False for the session's first turn, which creates it under `session_id`.
    resumed: bool
    mcp_file: Path
    disallowed: list[str]
    skills: SkillsPlugin
    link: TurnLink
    store: Any
    thinking: bool


def agent_options(launch: AgentLaunch) -> ClaudeAgentOptions:
    session: dict[str, Any] = (
        {"resume": launch.session_id}
        if launch.resumed
        else {"session_id": launch.session_id}
    )
    if launch.thinking:
        # Without `summarized`, Claude Code omits the thinking text.
        session["thinking"] = {"type": "adaptive", "display": "summarized"}
    return launch_options(
        launch.binary,
        proxy_url=launch.proxy_url,
        model=launch.model,
        cwd=str(launch.folder),
        tools=TOOLS,
        mcp_servers=str(launch.mcp_file),
        disallowed_tools=launch.disallowed,
        plugins=[{"type": "local", "path": str(launch.skills.root)}],
        skills=sorted(launch.skills.names),
        system_prompt=for_claude(agent_prompt()),
        hooks={
            "PreToolUse": [
                HookMatcher(hooks=[launch.link.pre_tool_use], timeout=HOOK_SECONDS)
            ]
        },
        can_use_tool=launch.link.can_use_tool,
        include_partial_messages=True,
        session_store=launch.store,
        env={
            "MAX_MCP_OUTPUT_TOKENS": str(MAX_RESULT_TOKENS),
            "MCP_TOOL_TIMEOUT": str(TOOL_CALL_MS),
            "MCP_TIMEOUT": str(CONNECT_SECONDS * 1000),
        },
        **session,
    )
