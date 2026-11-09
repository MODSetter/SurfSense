"""What an agent run's Claude Code starts with: the thread's folder, SurfSense's tools and rules."""

from pathlib import Path

import pytest

from modules.agent.engines.claude_code.agent_options import AgentLaunch, agent_options
from modules.agent.engines.claude_code.approvals import Approvals
from modules.agent.engines.claude_code.skills_plugin import SkillsPlugin
from modules.agent.engines.claude_code.turn_link import TurnLink
from modules.agent.plugin_tools.connect_limit import CONNECT_SECONDS

pytestmark = pytest.mark.unit
BINARY = Path("/home/ada/.local/bin/claude")


def _launch(tmp_path: Path, *, resumed: bool = False) -> AgentLaunch:
    return AgentLaunch(
        binary=BINARY,
        proxy_url="http://127.0.0.1:5000",
        folder=tmp_path / "threads" / "7",
        model="claude-sonnet-5-5",
        session_id="s-1",
        resumed=resumed,
        mcp_file=tmp_path / "mcp-1.json",
        disallowed=["mcp__notion__delete_page"],
        skills=SkillsPlugin(
            tmp_path / "plugin",
            tmp_path / "plugin" / "skills",
            frozenset({"surfsense:surfsense-documents"}),
        ),
        link=TurnLink(7, Approvals()),
        store=None,
        thinking=False,
    )


def test_claude_code_works_in_the_threads_folder_with_surfsenses_tools(
    tmp_path: Path,
) -> None:
    """No Bash, web or subagents: the tools opencode is allowed, and SurfSense's skills."""
    options = agent_options(_launch(tmp_path))

    assert options.cwd == str(tmp_path / "threads" / "7")
    assert options.model == "claude-sonnet-5-5"
    assert options.tools == ["Read", "Glob", "Grep", "Write", "Edit", "Skill"]
    assert options.mcp_servers == str(tmp_path / "mcp-1.json")
    assert options.disallowed_tools == ["mcp__notion__delete_page"]
    assert options.plugins == [{"type": "local", "path": str(tmp_path / "plugin")}]
    assert options.skills == ["surfsense:surfsense-documents"]


def test_every_call_meets_surfsenses_gate_and_the_users_setup_never_applies(
    tmp_path: Path,
) -> None:
    """As every Claude Code run: no ~/.claude settings, and `default` permission mode."""
    options = agent_options(_launch(tmp_path))

    assert options.setting_sources == []
    assert options.permission_mode == "default"
    assert options.can_use_tool is not None
    (matcher,) = options.hooks["PreToolUse"]
    assert matcher.hooks


def test_the_first_turn_names_the_session_and_later_ones_resume_it(
    tmp_path: Path,
) -> None:
    """SurfSense chooses the id, so the thread knows its session before Claude Code runs."""
    first = agent_options(_launch(tmp_path))
    later = agent_options(_launch(tmp_path, resumed=True))

    assert (first.session_id, first.resume) == ("s-1", None)
    assert (later.session_id, later.resume) == (None, "s-1")


def test_traffic_goes_through_claude_codes_proxy_and_results_reach_the_model(
    tmp_path: Path,
) -> None:
    """A long result is never written into ~/.claude; a plugin's long call is not cut short."""
    env = agent_options(_launch(tmp_path)).env

    assert env["HTTPS_PROXY"] == "http://127.0.0.1:5000"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert int(env["MAX_MCP_OUTPUT_TOKENS"]) > 25_000
    assert int(env["MCP_TOOL_TIMEOUT"]) >= 300_000


def test_claude_code_gives_up_on_a_plugin_when_opencode_does(tmp_path: Path) -> None:
    """One limit, so a slow plugin is reported alike whichever engine runs the thread."""
    env = agent_options(_launch(tmp_path)).env

    assert int(env["MCP_TIMEOUT"]) == CONNECT_SECONDS * 1000
