from pathlib import Path

import pytest

from modules.llm.subscriptions.claude.launch import launch_options

pytestmark = pytest.mark.unit
BINARY = Path("/home/ada/.local/bin/claude")


def test_every_run_is_isolated_from_the_users_claude_setup() -> None:
    """The user's settings, CLAUDE.md, MCP servers and permission mode never apply."""
    options = launch_options(BINARY, proxy_url=None)

    assert options.cli_path == str(BINARY)
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.verbatim_prompts is True
    assert options.permission_mode == "default"


def test_the_caller_sets_what_differs_per_run() -> None:
    """Chat and the agent pass their own tools, prompt and turn limit."""
    options = launch_options(
        BINARY,
        proxy_url=None,
        tools=[],
        system_prompt="You are SurfSense.",
        max_turns=1,
    )

    assert options.tools == []
    assert options.system_prompt == "You are SurfSense."
    assert options.max_turns == 1


@pytest.mark.parametrize(
    "fixed",
    [
        "cli_path",
        "setting_sources",
        "strict_mcp_config",
        "verbatim_prompts",
        "permission_mode",
    ],
)
def test_a_caller_cannot_override_isolation(fixed: str) -> None:
    """Losing one of these would let the user's own Claude setup, or `auto` mode, in."""
    with pytest.raises(ValueError, match=fixed):
        launch_options(BINARY, proxy_url=None, **{fixed: None})


def test_a_key_in_the_environment_never_replaces_the_plan() -> None:
    """Measured: with ANTHROPIC_API_KEY set, Claude Code bills the key, not the plan."""
    options = launch_options(BINARY, proxy_url=None, env={"ANTHROPIC_API_KEY": "sk-x"})

    assert options.env["ANTHROPIC_API_KEY"] == ""


def test_claude_code_sends_nothing_but_model_calls() -> None:
    """Without this, it also reports to an error-tracking host."""
    options = launch_options(BINARY, proxy_url=None)

    assert options.env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"


def test_its_traffic_goes_through_surfsenses_proxy() -> None:
    """Loopback stays direct, so the agent reaches SurfSense's own MCP endpoint."""
    options = launch_options(BINARY, proxy_url="http://127.0.0.1:4711")

    assert options.env["HTTPS_PROXY"] == "http://127.0.0.1:4711"
    assert options.env["HTTP_PROXY"] == "http://127.0.0.1:4711"
    assert options.env["NO_PROXY"] == "127.0.0.1,localhost"


def test_a_caller_cannot_route_around_the_proxy() -> None:
    """A run may add environment, never undo the proxy."""
    options = launch_options(
        BINARY, proxy_url="http://127.0.0.1:4711", env={"HTTPS_PROXY": "", "TZ": "UTC"}
    )

    assert options.env["HTTPS_PROXY"] == "http://127.0.0.1:4711"
    assert options.env["TZ"] == "UTC"
