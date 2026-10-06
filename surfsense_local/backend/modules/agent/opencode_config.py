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
# The file electron/src/main/sidecars/opencode.ts watches, in the agent folder.
CONFIG_FILE = "opencode.json"

# opencode never asks for more than this per answer, whatever the limit says.
OUTPUT_CAP = 32_000
# The room compaction keeps free, unless a single answer needs less than that.
RESERVE_FLOOR = 8_192
# Once a reply has started; long enough for a CPU to read a long prompt, short
# enough that a model which hangs mid-reply still ends the turn.
CHUNK_TIMEOUT_MS = 30 * 60 * 1000

# The skills SurfSense ships: how to write a document script (ADR 0039).
DOCUMENTS_SKILL = "surfsense-documents"
# Which PDF tool fits a request, and how pages are named.
PDF_SKILL = "surfsense-pdf"


def skills_folder() -> Path:
    """The shipped skills, inside the API's own files when frozen too."""
    return Path(files("modules.agent").joinpath("skills"))


def _permission(skills: Path) -> dict[str, Any]:
    """What the agent may do; the last matching rule wins, so each allow follows the deny it narrows."""
    return {
        # Document scripts reach the runner through a SurfSense tool (ADR 0039).
        "bash": "deny",
        # opencode matches an edit's path relative to the project root, which for a
        # folder outside git is "/", so the rule names the folder from any root.
        # "*" also spans folders, so the denies after it refuse paths that only
        # contain a thread's outputs/: a mirrored folder named "outputs" must not
        # open sources/, opencode loads agent definitions from .opencode/ and
        # skills from the skills folder, and every thread reads opencode's
        # tool-output folder. Another thread's outputs/ is outside this thread's
        # folder, which external_directory refuses.
        "edit": {
            "*": "deny",
            "*/agent/threads/*/outputs/*": "allow",
            "*/agent/threads/*/sources/*": "deny",
            "*/.opencode/*": "deny",
            "*/opencode/tool-output/*": "deny",
            f"*{skills.relative_to(skills.anchor).as_posix()}/*": "deny",
            # opencode reads these as instructions. Case-insensitive on Windows
            # only; the variants cover macOS.
            **{
                f"*{name}": "deny"
                for name in (
                    "AGENTS.md",
                    "agents.md",
                    "Agents.md",
                    "CONTEXT.md",
                    "context.md",
                    "Context.md",
                    "CLAUDE.md",
                    "claude.md",
                    "Claude.md",
                )
            },
        },
        # Only the skills folder, which a skill may point into. On macOS and Linux
        # opencode checks an absolute path as written, so "<skills>/../.." would
        # match the allow without the ".." deny. opencode's own folder for long
        # tool output stays open too: it allows that folder after these rules
        # unless one denies it by name (agent/agent.ts), so no rule here covers it.
        "external_directory": {
            "*": "deny",
            str(skills / "*"): "allow",
            "*/../*": "deny",
        },
        "webfetch": "deny",
        "websearch": "deny",
        # Child sessions would wait on the same single llama-server slot.
        "task": "deny",
        # Asks through a form SurfSense does not show in this phase.
        "question": "deny",
        # Not opencode's built-in skills, nor any the user installed for their own opencode.
        "skill": {
            "*": "deny",
            DOCUMENTS_SKILL: "allow",
            PDF_SKILL: "allow",
        },
    }


@dataclass(frozen=True)
class AgentSetup:
    """What opencode is configured from: the model, its window, and the way to it."""

    model: str
    window: int
    # Declared to opencode, which otherwise swaps each image `read` returns for an error text.
    reads_images: bool
    endpoint_url: str
    launch_key: str


def opencode_config(setup: AgentSetup) -> dict[str, Any]:
    """The whole configuration, from what the API knows about the selected model."""
    output = min(setup.window // 4, OUTPUT_CAP)
    model_ref = f"{PROVIDER}/{setup.model}"
    skills = skills_folder().resolve()
    permission = _permission(skills)
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
                "models": {setup.model: _model_entry(setup, output)},
            }
        },
        "skills": {"paths": [str(skills)]},
        "permission": permission,
        "agent": {
            AGENT: {
                "mode": "primary",
                "description": "Works on the user's sources in SurfSense",
                "prompt": agent_prompt(),
                "permission": permission,
            }
        },
    }


def _model_entry(setup: AgentSetup, output: int) -> dict[str, Any]:
    """The one model opencode may use, with what it accepts and its limits."""
    entry: dict[str, Any] = {
        "name": setup.model,
        "tool_call": True,
        # With input set, compaction honours `reserved`; without it, it does not.
        "limit": {"context": setup.window, "input": setup.window, "output": output},
    }
    if setup.reads_images:
        entry["modalities"] = {"input": ["text", "image"], "output": ["text"]}
        entry["attachment"] = True
    return entry


def declares_image_input(path: Path) -> bool:
    """Whether the configuration on disk lets the model see the images `read` opens.

    Without the declaration opencode swaps each image for an error text, so an
    image made for the model would be wasted; no configuration declares nothing.
    """
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    models = config.get("provider", {}).get(PROVIDER, {}).get("models", {})
    return any(entry.get("attachment") is True for entry in models.values())


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
