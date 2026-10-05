"""The configuration opencode runs with, as the file it reads."""

import json
import os
import re
import stat
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
    )


def written(path: Path) -> dict:
    """The configuration as opencode will read it."""
    return json.loads(path.read_text())


def test_opencode_reaches_only_the_model_endpoint_with_the_launch_key(
    tmp_path: Path,
) -> None:
    """Every model is reached through SurfSense, so keys and egress checks stay there."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    provider = config["provider"]["surfsense"]
    assert provider["npm"] == "@ai-sdk/openai-compatible"
    assert provider["options"]["baseURL"] == ENDPOINT
    assert provider["options"]["apiKey"] == "launch-key"
    assert config["enabled_providers"] == ["surfsense"]


def test_every_request_names_the_selected_model_titles_included(tmp_path: Path) -> None:
    """A second model would unload the first: the router holds one at a time."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(model="Qwen3-8B-UD-Q4_K_XL"))

    config = written(path)
    assert config["model"] == "surfsense/Qwen3-8B-UD-Q4_K_XL"
    assert config["small_model"] == "surfsense/Qwen3-8B-UD-Q4_K_XL"
    assert (
        config["provider"]["surfsense"]["models"]["Qwen3-8B-UD-Q4_K_XL"]["tool_call"]
        is True
    )


def test_a_model_that_reads_images_is_shown_the_pages_the_agent_opens(
    tmp_path: Path,
) -> None:
    """Without image input declared, opencode swaps each image `read` returns for an error text."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(reads_images=True))

    model = next(iter(written(path)["provider"]["surfsense"]["models"].values()))
    assert model["modalities"] == {"input": ["text", "image"], "output": ["text"]}
    assert model["attachment"] is True


def test_a_model_that_reads_no_images_declares_none(tmp_path: Path) -> None:
    """opencode then tells the model it cannot see the image, rather than sending one it refuses."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(reads_images=False))

    model = next(iter(written(path)["provider"]["surfsense"]["models"].values()))
    assert "modalities" not in model
    assert "attachment" not in model


@pytest.mark.parametrize(
    ("window", "output", "reserved"),
    [
        # The worked example: output is a quarter of the window, the reserve 8,192.
        (32768, 8192, 8192),
        # A large window: output stops at opencode's own 32,000 cap.
        (200000, 32000, 20000),
        # A small one: the reserve never exceeds what one answer can take.
        (8192, 2048, 2048),
    ],
)
def test_limits_follow_the_window_the_model_was_loaded_with(
    tmp_path: Path, window: int, output: int, reserved: int
) -> None:
    """Without limits opencode never compacts; with input set it honours the reserve."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(window=window))

    config = written(path)
    model = next(iter(config["provider"]["surfsense"]["models"].values()))
    assert model["limit"] == {"context": window, "input": window, "output": output}
    assert config["compaction"] == {"auto": True, "reserved": reserved}


def test_the_agent_has_no_shell_and_writes_only_to_outputs(tmp_path: Path) -> None:
    """Document scripts reach the runner through a tool; no other program runs (ADR 0039)."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    permission = config["permission"]
    assert permission["bash"] == "deny"
    # opencode spells an edit's path relative to "/", without the drive.
    (skills,) = config["skills"]["paths"]
    skills = Path(skills).relative_to(Path(skills).anchor).as_posix()
    agent = "Users/me/SurfSense/workspaces/1/agent"
    work = f"{agent}/threads/7"
    rules = permission["edit"]
    assert _opencode_decides(rules, f"{work}/outputs/report.md") == "allow"
    assert _opencode_decides(rules, f"{work}/outputs/drafts/a.md") == "allow"
    for refused in (
        f"{work}/sources/Plan [1].md",
        f"{work}/sources/Library/outputs/a.md",
        f"{work}/sources/R/outputs/a.md",
        f"{work}/sources/agent/threads/7/outputs/x.md",
        f"{work}/.opencode/agent/threads/7/outputs/x.md",
        f"{work}/outputs/agents.md",
        f"{work}/outputs/AGENTS.md",
        f"{work}/outputs/drafts/Context.md",
        f"{work}/outputs/CLAUDE.md",
        # Where every thread once worked.
        f"{agent}/outputs/a.md",
        f"{agent}/sources/Plan [1].md",
        "Users/me/SurfSense/agent/opencode/data/opencode/tool-output/agent/threads/7/outputs/x",
        f"{skills}/x/agent/threads/7/outputs/SKILL.md",
        "Users/me/elsewhere.md",
    ):
        assert _opencode_decides(rules, refused) == "deny", refused
    for tool in ("webfetch", "websearch", "task", "question"):
        assert permission[tool] == "deny", tool


def test_only_surfsenses_documents_skill_loads_from_the_shipped_folder(
    tmp_path: Path,
) -> None:
    """opencode's built-in skills and any the user installed stay out of SurfSense's agent."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    (skills,) = config["skills"]["paths"]
    assert (Path(skills) / "surfsense-documents" / "SKILL.md").is_file()
    assert list(config["permission"]["skill"].items()) == [
        ("*", "deny"),
        ("surfsense-documents", "allow"),
    ]


def test_outside_its_folder_the_agent_reads_only_the_skills(tmp_path: Path) -> None:
    """A skill may point at files beside it; every other folder outside stays shut."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    (skills,) = config["skills"]["paths"]
    assert list(config["permission"]["external_directory"].items()) == [
        ("*", "deny"),
        (str(Path(skills) / "*"), "allow"),
        ("*/../*", "deny"),
    ]


def _opencode_decides(rules: dict[str, str], folder_glob: str) -> str:
    """opencode's rule: '*' is any text, '\\' is '/', and the last rule that matches wins."""

    def matches(pattern: str) -> bool:
        pattern = re.escape(pattern.replace("\\", "/")).replace(r"\*", ".*")
        return re.fullmatch(pattern, folder_glob.replace("\\", "/"), re.S) is not None

    return [action for pattern, action in rules.items() if matches(pattern)][-1]


def test_a_path_that_climbs_out_of_the_skills_folder_is_refused(
    tmp_path: Path,
) -> None:
    """On macOS and Linux opencode checks an absolute path as written, '..' and all."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    (skills,) = config["skills"]["paths"]
    rules = config["permission"]["external_directory"]
    skills = skills.replace("\\", "/")
    assert _opencode_decides(rules, f"{skills}/surfsense-documents/*") == "allow"
    climbing = f"{skills}/../../../../../Users/me/.ssh/*"
    assert _opencode_decides(rules, climbing) == "deny"


def test_sharing_snapshots_and_updates_are_off_and_waiting_is_long(
    tmp_path: Path,
) -> None:
    """A local model can take minutes before its first byte, past opencode's 300 s."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    assert (config["share"], config["snapshot"], config["autoupdate"]) == (
        "disabled",
        False,
        False,
    )
    options = config["provider"]["surfsense"]["options"]
    assert options["headerTimeout"] is False
    assert options["chunkTimeout"] > 300_000


def test_surfsenses_own_agent_is_the_default(tmp_path: Path) -> None:
    """SurfSense's prompt replaces opencode's coding one, within its length budget."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    config = written(path)
    agent = config["agent"][config["default_agent"]]
    assert agent["mode"] == "primary"
    assert "outputs" in agent["prompt"]
    assert len(agent["prompt"]) < 4000


@pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX file modes")
def test_only_surfsense_can_read_the_file_that_holds_the_key(tmp_path: Path) -> None:
    """The launch key opens the model endpoint, so no other user may read it."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_an_unchanged_configuration_is_not_rewritten(tmp_path: Path) -> None:
    """Every rewrite restarts opencode, ending whatever turn is running."""
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
    prompt = config["agent"][config["default_agent"]]["prompt"]
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
    prompt = config["agent"][config["default_agent"]]["prompt"]
    assert "shell command" not in prompt.lower()
    assert "approve" not in prompt.lower()


@pytest.mark.parametrize("reads_images", [True, False])
def test_the_written_file_says_whether_the_model_is_shown_images(
    tmp_path: Path, reads_images: bool
) -> None:
    """The render tool draws previews only for a model opencode will show them to."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup(reads_images=reads_images))

    assert declares_image_input(path) is reads_images
    assert declares_image_input(tmp_path / "none.json") is False
