"""The configuration opencode runs with, as the file it reads."""

import json
import os
import stat
from pathlib import Path

import pytest

from modules.agent.opencode_config import AgentSetup, write_opencode_config

pytestmark = pytest.mark.unit

ENDPOINT = "http://127.0.0.1:8123/agent/model/v1"


def setup(window: int = 32768, model: str = "Qwen3-8B-UD-Q4_K_XL") -> AgentSetup:
    """What the API knows when it first needs the agent."""
    return AgentSetup(
        model=model, window=window, endpoint_url=ENDPOINT, launch_key="launch-key"
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


def test_shell_commands_ask_and_files_are_written_only_to_outputs(
    tmp_path: Path,
) -> None:
    """The sources stay read-only and every command waits for the user."""
    path = tmp_path / "opencode.json"
    write_opencode_config(path, setup())

    permission = written(path)["permission"]
    assert permission["bash"] == "ask"
    # The last matching rule wins, so the allow comes after the deny.
    assert list(permission["edit"].items()) == [("*", "deny"), ("outputs/*", "allow")]
    assert permission["external_directory"] == "deny"
    for tool in ("webfetch", "websearch", "task", "question", "skill"):
        assert permission[tool] == "deny", tool


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
