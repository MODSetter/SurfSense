"""The configuration opencode runs with, written where Electron watches for it.

Electron starts opencode when this file appears and restarts it whenever it
changes, ending any turn in progress, so a write that changes nothing is skipped.
Keys are opencode 1.x's (docs/proposals/agent/03-opencode.md, Configuration).
"""

import json
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

PROVIDER = "surfsense"
AGENT = "surfsense"

# opencode never asks for more than this per answer, whatever the limit says.
OUTPUT_CAP = 32_000
# The room compaction keeps free, unless a single answer needs less than that.
RESERVE_FLOOR = 8_192
# Once a reply has started; long enough for a CPU to read a long prompt, short
# enough that a model which hangs mid-reply still ends the turn.
CHUNK_TIMEOUT_MS = 30 * 60 * 1000

# The last matching rule wins, so each allow follows the deny it narrows.
PERMISSION: dict[str, Any] = {
    "bash": "ask",
    # opencode matches an edit's path relative to the project root, which for a
    # folder outside git is "/", so the rule names the folder from any root.
    "edit": {"*": "deny", "*/agent/outputs/*": "allow"},
    "external_directory": "deny",
    "webfetch": "deny",
    "websearch": "deny",
    # Child sessions would wait on the same single llama-server slot.
    "task": "deny",
    # Asks through a form SurfSense does not show in this phase.
    "question": "deny",
    # SurfSense ships no skills.
    "skill": "deny",
}


@dataclass(frozen=True)
class AgentSetup:
    """What opencode is configured from: the model, its window, and the way to it."""

    model: str
    window: int
    endpoint_url: str
    launch_key: str


def opencode_config(setup: AgentSetup) -> dict[str, Any]:
    """The whole configuration, from what the API knows about the selected model."""
    output = min(setup.window // 4, OUTPUT_CAP)
    model_ref = f"{PROVIDER}/{setup.model}"
    return {
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        "snapshot": False,
        "autoupdate": False,
        "enabled_providers": [PROVIDER],
        "model": model_ref,
        "small_model": model_ref,
        "default_agent": AGENT,
        "compaction": {
            "auto": True,
            "reserved": min(output, max(setup.window // 10, RESERVE_FLOOR)),
        },
        "provider": {
            PROVIDER: {
                "npm": "@ai-sdk/openai-compatible",
                "name": "SurfSense",
                "options": {
                    "baseURL": setup.endpoint_url,
                    "apiKey": setup.launch_key,
                    "headerTimeout": False,
                    "chunkTimeout": CHUNK_TIMEOUT_MS,
                },
                "models": {
                    setup.model: {
                        "name": setup.model,
                        "tool_call": True,
                        # With input set, compaction honours `reserved`; without it, it does not.
                        "limit": {
                            "context": setup.window,
                            "input": setup.window,
                            "output": output,
                        },
                    }
                },
            }
        },
        "permission": PERMISSION,
        "agent": {
            AGENT: {
                "mode": "primary",
                "description": "Works on the user's sources in SurfSense",
                "prompt": agent_prompt(),
                "permission": PERMISSION,
            }
        },
    }


def agent_prompt() -> str:
    """SurfSense's instructions to the agent, in place of opencode's coding prompt."""
    return (
        files("modules.agent")
        .joinpath("prompts", "agent.md")
        .read_text(encoding="utf-8")
        .strip()
    )


def write_opencode_config(path: Path, setup: AgentSetup) -> bool:
    """Write the configuration; False, and nothing written, when it is already on disk.

    Written whole and readable by this user alone: it holds the launch key, and
    opencode must never read half a file.
    """
    text = json.dumps(opencode_config(setup), indent=2) + "\n"
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(text)
    os.replace(partial, path)
    return True
