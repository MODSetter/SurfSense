"""The configuration opencode runs with, written where Electron watches for it.

Electron starts opencode when this file appears; opencode watches it and loads a
rewrite within a second, so a write that changes nothing is skipped. Keys are
opencode 2.x's own (docs/architecture/agent.md, The configuration).
"""

import json
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from modules.llm.catalog.remote.manifest.lookup import CallRoute

PROVIDER = "surfsense"
AGENT = "surfsense"
# The agent opencode would name a session with; SurfSense names every session itself.
TITLE_AGENT = "title"
# The file sidecars/opencode.ts watches, in the agent folder.
CONFIG_FILE = "opencode.json"

# opencode never asks for more than this per answer, whatever the limit says.
OUTPUT_CAP = 32_000
# The room compaction keeps free, unless a single answer needs less than that.
RESERVE_FLOOR = 8_192
# Recent messages compaction keeps word for word beside its summary: an eighth of
# the window, as opencode's 15,000 is half a 32k window and compacts again at once.
KEEP_SHARE = 8
KEEP_CAP = 15_000
# Once a reply has started; long enough for a CPU to read a long prompt, short
# enough that a model which hangs mid-reply still ends the turn.
CHUNK_TIMEOUT_MS = 30 * 60 * 1000

# Built into opencode: its OpenAI provider calls /responses; the compatible one, /chat/completions.
PROVIDER_PACKAGES: dict[CallRoute, str] = {
    "chat_completions": "@opencode/ai/providers/openai-compatible",
    "responses": "@opencode/ai/providers/openai",
}

# opencode's own plugins left out: the first three probe Ollama, LM Studio and
# vLLM on loopback every 30 s, and the last two list opencode's own skills and
# tell the model to use `execute`. An id opencode does not know is ignored.
PLUGINS_OFF = [
    "-opencode.provider.ollama",
    "-opencode.provider.lmstudio",
    "-opencode.provider.vllm",
    "-opencode.skill",
    "-opencode.tools",
]

# The skills SurfSense ships: how to write a document script (ADR 0039), and
# how to revise the user's own file.
DOCUMENTS_SKILL = "surfsense-documents"
REVISIONS_SKILL = "surfsense-revisions"
# How to analyse spreadsheets and CSVs with surfsense_analyze_data.
DATA_SKILL = "surfsense-data"
# Which PDF tool fits a request, and how pages are named.
PDF_SKILL = "surfsense-pdf"
# How to write a web page and keep it with surfsense_save_page (ADR 0066).
HTML_SKILL = "surfsense-html"
SKILLS = (DOCUMENTS_SKILL, REVISIONS_SKILL, DATA_SKILL, PDF_SKILL, HTML_SKILL)

# Denied as permissions, which also leave the tool out of what the model is
# offered: document scripts reach the runner through a SurfSense tool (ADR 0039),
# Code Mode's `execute` would run model-written code with a fetch no rule covers,
# child sessions would wait on the same single llama-server slot, and a question
# asks through a form SurfSense does not show.
DENIED = ("shell", "execute", "subagent", "question", "webfetch", "websearch")
# Repeated as policies, which no session rule or saved approval can lift.
DENIED_FOR_GOOD = ("shell", "webfetch", "websearch", "subagent")


def skills_folder() -> Path:
    """The shipped skills, inside the API's own files when frozen too."""
    return Path(files("modules.agent").joinpath("skills"))


def tool_output_folder(agent_dir: Path) -> Path:
    """Where opencode keeps a long tool result whole: its data folder, under the agent's."""
    return agent_dir / "opencode" / "data" / "opencode" / "tool-output"


def _rule(action: str, resource: str, effect: str) -> dict[str, str]:
    return {"action": action, "resource": resource, "effect": effect}


def _permissions(skills: Path, tool_output: Path) -> list[dict[str, str]]:
    """What the agent may do; the last matching rule wins, so each allow follows the deny it narrows.

    An edit inside the thread's folder is matched relative to it (`outputs/a.md`),
    and one outside it absolutely, which `external_directory` refuses first. `*`
    spans folders, so `sources/Lib/outputs/x` never matches `outputs/*`.
    """
    return [
        *(_rule(action, "*", "deny") for action in DENIED),
        _rule("edit", "*", "deny"),
        _rule("edit", "outputs/*", "allow"),
        # opencode reads these as instructions or agent definitions. Case-insensitive
        # on Windows only; the variants cover macOS.
        *(
            _rule("edit", name, "deny")
            for name in (
                "*AGENTS.md",
                "*agents.md",
                "*Agents.md",
                ".opencode/*",
                "*/.opencode/*",
            )
        ),
        # 2.x allows other folders unless told, and no longer opens its own
        # tool-output folder by itself; a skill may point into the skills folder.
        _rule("external_directory", "*", "deny"),
        _rule("external_directory", f"{skills.as_posix()}/*", "allow"),
        _rule("external_directory", f"{tool_output.as_posix()}/*", "allow"),
        # Not opencode's built-in skills, nor any the user installed for their own opencode.
        _rule("skill", "*", "deny"),
        *(_rule("skill", name, "allow") for name in SKILLS),
    ]


@dataclass(frozen=True)
class AgentSetup:
    """What opencode is configured from: the model, its window, and the way to it."""

    model: str
    window: int
    # Declared to opencode, which otherwise assumes a model it does not know reads images.
    reads_images: bool
    endpoint_url: str
    launch_key: str
    # Where the model answers; opencode then speaks that route to the endpoint.
    route: CallRoute


def opencode_config(setup: AgentSetup, agent_dir: Path) -> dict[str, Any]:
    """The whole configuration, from what the API knows about the selected model."""
    output = min(setup.window // 4, OUTPUT_CAP)
    model = {"providerID": PROVIDER, "model": setup.model}
    skills = skills_folder().resolve()
    return {
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        "snapshots": False,
        "update": "disable",
        "model": model,
        "default_agent": AGENT,
        "plugins": PLUGINS_OFF,
        "policies": [
            _rule("provider.use", "*", "deny"),
            _rule("provider.use", PROVIDER, "allow"),
            *(_rule("tool.use", tool, "deny") for tool in DENIED_FOR_GOOD),
        ],
        "compaction": {
            "auto": True,
            "buffer": min(output, max(setup.window // 10, RESERVE_FLOOR)),
            "keep": {"tokens": min(setup.window // KEEP_SHARE, KEEP_CAP)},
        },
        "providers": {
            PROVIDER: {
                "package": PROVIDER_PACKAGES[setup.route],
                "name": "SurfSense",
                "settings": {
                    "baseURL": setup.endpoint_url,
                    "apiKey": setup.launch_key,
                    "headerTimeout": False,
                    "chunkTimeout": CHUNK_TIMEOUT_MS,
                },
                "models": {setup.model: _model_entry(setup, output)},
            }
        },
        "skills": [str(skills)],
        "permissions": _permissions(skills, tool_output_folder(agent_dir)),
        "agents": {
            AGENT: {"mode": "primary", "system": agent_prompt()},
            TITLE_AGENT: {"model": model},
        },
        # 2.x offers `todowrite` only with this; 1.x always did, and the thread
        # shows its steps as "Updated its plan". Experimental on purpose: if it
        # goes, todos turn off and nothing else breaks.
        "experimental": {"todo": True},
    }


def _model_entry(setup: AgentSetup, output: int) -> dict[str, Any]:
    """The one model opencode may use, with what it accepts and its limits."""
    return {
        "name": setup.model,
        "capabilities": {
            "tools": True,
            "input": ["text", "image"] if setup.reads_images else ["text"],
            "output": ["text"],
        },
        # With input set, compaction honours `buffer`; without it, it does not.
        "limit": {"context": setup.window, "input": setup.window, "output": output},
    }


def declares_image_input(path: Path) -> bool:
    """Whether the configuration on disk lets the model see the images `read` opens.

    Without the declaration a text-only model is sent each image anyway, or an
    image made for one that reads them is wasted; no configuration declares nothing.
    """
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    models = config.get("providers", {}).get(PROVIDER, {}).get("models", {})
    return any(
        "image" in entry.get("capabilities", {}).get("input", [])
        for entry in models.values()
    )


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
    opencode must never read half a file. It lives in the agent folder.
    """
    text = json.dumps(opencode_config(setup, path.parent), indent=2) + "\n"
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
