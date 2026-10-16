from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions


def launch_options(
    binary: Path, *, proxy_url: str | None, **per_run: Any
) -> ClaudeAgentOptions:
    """The only place options for a Claude Code run are built.

    `permission_mode` is fixed because Claude Code 2.1.301 defaults to `auto`,
    which approves tools without asking SurfSense.
    """
    fixed: dict[str, Any] = {
        "cli_path": str(binary),
        "setting_sources": [],
        "strict_mcp_config": True,
        "verbatim_prompts": True,
        "permission_mode": "default",
    }
    if clash := sorted(fixed.keys() & per_run.keys()):
        raise ValueError(f"a run cannot set {', '.join(clash)}")
    env = {**per_run.pop("env", {}), **claude_env(proxy_url)}
    return ClaudeAgentOptions(**fixed, env=env, **per_run)


def claude_env(proxy_url: str | None) -> dict[str, str]:
    """What every Claude Code process gets, a run or the status check alike.

    A key in the API's environment would silently replace the plan.
    """
    env = {"ANTHROPIC_API_KEY": "", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    if proxy_url is not None:
        env |= {
            "HTTPS_PROXY": proxy_url,
            "HTTP_PROXY": proxy_url,
            "NO_PROXY": "127.0.0.1,localhost",
        }
    return env
