"""The configuration opencode runs with, as the file it reads."""

import json
import os
import re
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from modules.agent.opencode_config import (
    AgentSetup,
    declares_image_input,
    write_opencode_config,
)

pytestmark = pytest.mark.unit

ENDPOINT = "http://127.0.0.1:8123/agent/model/v1"


def setup(
    window: int = 32768, model: str = "Qwen3-8B-UD-Q4_K_XL", reads_images: bool = False
) -> AgentSetup:
    """What the API knows when it first needs the agent."""
    return AgentSetup(
        model=model,
        window=window,
        reads_images=reads_images,
        endpoint_url=ENDPOINT,
        launch_key="launch-key",
        route="chat_completions",
    )


def written(path: Path) -> dict:
    """The configuration as opencode will read it."""
    return json.loads(path.read_text())


def _model(config: dict) -> dict:
    return next(iter(config["providers"]["surfsense"]["models"].values()))


def test_opencode_reaches_only_the_model_endpoint_with_the_launch_key(
    tmp_path: Path,
) -> None:
    """Every model is reached through SurfSense, so keys and egress checks stay there."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    provider = config["providers"]["surfsense"]
    assert provider["package"] == "@opencode/ai/providers/openai-compatible"
    assert provider["settings"]["baseURL"] == ENDPOINT
    assert provider["settings"]["apiKey"] == "launch-key"
    assert config["policies"][:2] == [
        {"action": "provider.use", "resource": "*", "effect": "deny"},
        {"action": "provider.use", "resource": "surfsense", "effect": "allow"},
    ]


def test_a_responses_model_is_reached_through_openais_own_provider(
    tmp_path: Path,
) -> None:
    """opencode then calls the endpoint's /responses, still SurfSense's, still under the launch key."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, replace(setup(), route="responses"))

    provider = written(path)["providers"]["surfsense"]
    assert provider["package"] == "@opencode/ai/providers/openai"
    assert provider["settings"]["baseURL"] == ENDPOINT
    assert provider["settings"]["apiKey"] == "launch-key"


def test_every_request_names_the_selected_model_titles_included(tmp_path: Path) -> None:
    """A second model would unload the first: the router holds one at a time."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(model="Qwen3-8B-UD-Q4_K_XL"))

    config = written(path)
    chosen = {"providerID": "surfsense", "model": "Qwen3-8B-UD-Q4_K_XL"}
    assert config["model"] == chosen
    assert config["agents"]["title"]["model"] == chosen
    assert _model(config)["capabilities"]["tools"] is True


def test_a_model_that_reads_images_is_shown_the_pages_the_agent_opens(
    tmp_path: Path,
) -> None:
    """Without image input declared, opencode swaps each image `read` returns for an error text."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(reads_images=True))

    assert _model(written(path))["capabilities"]["input"] == ["text", "image"]


def test_a_model_that_reads_no_images_says_so(tmp_path: Path) -> None:
    """opencode assumes a model it does not know reads images, and would send it some."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(reads_images=False))

    assert _model(written(path))["capabilities"]["input"] == ["text"]


@pytest.mark.parametrize(
    ("window", "output", "buffer", "keep"),
    [
        # The worked example: output is a quarter of the window, the buffer 8,192.
        (32768, 8192, 8192, 4096),
        # A large window: output stops at opencode's own 32,000 cap, keep at its default.
        (200000, 32000, 20000, 15000),
        # A small one: the buffer never exceeds what one answer can take.
        (8192, 2048, 2048, 1024),
    ],
)
def test_limits_follow_the_window_the_model_was_loaded_with(
    tmp_path: Path, window: int, output: int, buffer: int, keep: int
) -> None:
    """Without limits opencode never compacts; with input set it honours the buffer,
    and keeps less than half a small window word for word."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(window=window))

    config = written(path)
    assert _model(config)["limit"] == {
        "context": window,
        "input": window,
        "output": output,
    }
    assert config["compaction"] == {
        "auto": True,
        "buffer": buffer,
        "keep": {"tokens": keep},
    }


def _decides(rules: list[dict], action: str, resource: str) -> str:
    """opencode's rule (core/src/permission.ts): '*' is any text, '\\' is '/', and
    the last rule that matches wins; none asks."""

    def matches(pattern: str) -> bool:
        pattern = re.escape(pattern.replace("\\", "/")).replace(r"\*", ".*")
        return re.fullmatch(pattern, resource.replace("\\", "/"), re.S) is not None

    effects = [
        rule["effect"]
        for rule in rules
        if rule["action"] == action and matches(rule["resource"])
    ]
    return effects[-1] if effects else "ask"


def test_the_agent_has_no_shell_and_writes_only_to_outputs(tmp_path: Path) -> None:
    """Document scripts reach the runner through a tool; no other program runs (ADR 0039).

    An edit inside the thread's folder is named relative to it.
    """
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    rules = written(path)["permissions"]
    assert _decides(rules, "edit", "outputs/report.md") == "allow"
    assert _decides(rules, "edit", "outputs/drafts/a.md") == "allow"
    for refused in (
        "sources/Plan [1].md",
        "sources/Library/outputs/a.md",
        "sources/agent/threads/7/outputs/x.md",
        ".opencode/agent/threads/7/outputs/x.md",
        "outputs/.opencode/agents/x.md",
        "outputs/agents.md",
        "outputs/AGENTS.md",
        "AGENTS.md",
        "C:/Users/me/SurfSense/agent/threads/8/outputs/a.md",
        "/Users/me/elsewhere.md",
    ):
        assert _decides(rules, "edit", refused) == "deny", refused
    for tool in ("shell", "execute", "subagent", "question", "webfetch", "websearch"):
        assert _decides(rules, tool, "*") == "deny", tool


def test_no_session_rule_can_lift_the_shell_or_the_network(tmp_path: Path) -> None:
    """Policies hold where a saved approval or a session's own rules could not."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    policies = written(path)["policies"]
    assert [
        p["resource"]
        for p in policies
        if p["action"] == "tool.use" and p["effect"] == "deny"
    ] == ["shell", "webfetch", "websearch", "subagent"]


@pytest.mark.parametrize("route", ["chat_completions", "responses"])
def test_only_surfsenses_own_skills_load_from_the_shipped_folder(
    tmp_path: Path, route: str
) -> None:
    """opencode's built-in skills and any the user installed stay out of SurfSense's agent,
    whichever route the model answers on."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, replace(setup(), route=route))

    config = written(path)
    (skills,) = config["skills"]
    names = (
        "surfsense-documents",
        "surfsense-revisions",
        "surfsense-data",
        "surfsense-pdf",
        "surfsense-html",
    )
    for name in names:
        assert (Path(skills) / name / "SKILL.md").is_file()
    rules = config["permissions"]
    assert _decides(rules, "skill", "opencode") == "deny"
    for name in names:
        assert _decides(rules, "skill", name) == "allow", name
    assert "-opencode.skill" in config["plugins"]


def test_outside_its_folder_the_agent_reads_only_the_skills_and_long_output(
    tmp_path: Path,
) -> None:
    """A skill may point at files beside it, and opencode names the file a cut
    result was kept in; every other folder outside stays shut."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    rules = config["permissions"]
    (skills,) = config["skills"]
    skills = skills.replace("\\", "/")
    kept = (tmp_path / "opencode" / "data" / "opencode" / "tool-output").as_posix()
    assert _decides(rules, "external_directory", f"{skills}/surfsense-pdf/*") == "allow"
    assert _decides(rules, "external_directory", f"{kept}/*") == "allow"
    for refused in (f"{tmp_path.as_posix()}/*", "/Users/me/.ssh/*"):
        assert _decides(rules, "external_directory", refused) == "deny", refused


def test_opencodes_own_plugins_stay_out(tmp_path: Path) -> None:
    """Loopback probes for other model servers, and a hint to use `execute`."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    assert written(path)["plugins"] == [
        "-opencode.provider.ollama",
        "-opencode.provider.lmstudio",
        "-opencode.provider.vllm",
        "-opencode.skill",
        "-opencode.tools",
    ]


def test_sharing_snapshots_and_updates_are_off_and_waiting_is_long(
    tmp_path: Path,
) -> None:
    """A local model can take minutes before its first byte, past opencode's 300 s."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    assert (config["share"], config["snapshots"], config["update"]) == (
        "disabled",
        False,
        "disable",
    )
    settings = config["providers"]["surfsense"]["settings"]
    assert settings["headerTimeout"] is False
    assert settings["chunkTimeout"] > 300_000


def test_the_agent_keeps_its_plan(tmp_path: Path) -> None:
    """2.x offers `todowrite` only when asked to, and the thread shows its plan."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    assert written(path)["experimental"] == {"todo": True}


def test_surfsenses_own_agent_is_the_default(tmp_path: Path) -> None:
    """SurfSense's prompt replaces opencode's coding one, within its length budget."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    agent = config["agents"][config["default_agent"]]
    assert agent["mode"] == "primary"
    assert "outputs" in agent["system"]
    assert len(agent["system"]) < 4000


@pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX file modes")
def test_only_surfsense_can_read_the_file_that_holds_the_key(tmp_path: Path) -> None:
    """The launch key opens the model endpoint, so no other user may read it."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_an_unchanged_configuration_is_not_rewritten(tmp_path: Path) -> None:
    """opencode reloads on every write, which a turn then waits on."""
    path = tmp_path / "opencode.json"
    assert write_opencode_config(path, setup()) is True
    before = path.stat().st_mtime_ns

    assert write_opencode_config(path, setup()) is False
    assert path.stat().st_mtime_ns == before
    assert write_opencode_config(path, setup(window=16384)) is True


def test_the_prompt_names_the_tools_as_opencode_shows_them(tmp_path: Path) -> None:
    """opencode prefixes each MCP tool with its server; a prompt naming another tool teaches nothing."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    prompt = config["agents"][config["default_agent"]]["system"]
    for tool in (
        "surfsense_search_sources",
        "surfsense_create_artifact",
        "surfsense_render_document",
        "surfsense_read_document",
        "surfsense_list_images",
    ):
        assert tool in prompt, tool


def test_the_prompt_asks_for_no_shell(tmp_path: Path) -> None:
    """The shell is denied, so a prompt that offers one sends the model at a wall."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    prompt = config["agents"][config["default_agent"]]["system"]
    assert "shell command" not in prompt.lower()
    assert "approve" not in prompt.lower()


@pytest.mark.parametrize("route", ["chat_completions", "responses"])
@pytest.mark.parametrize("reads_images", [True, False])
def test_the_written_file_says_whether_the_model_is_shown_images(
    tmp_path: Path, reads_images: bool, route: str
) -> None:
    """The render tool draws previews only for a model opencode will show them to, on either route."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, replace(setup(reads_images=reads_images), route=route))

    assert declares_image_input(path) is reads_images
    assert declares_image_input(tmp_path / "none.json") is False
