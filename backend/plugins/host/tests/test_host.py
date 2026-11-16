import shutil
from pathlib import Path

import httpx2
import pytest

from host.app import host_app
from host.tests.mcp_calls import call, tool_names
from host.tests.serving import serving

SAMPLES = Path(__file__).parent / "sample_plugins"


def test_the_host_answers_its_health_check() -> None:
    with serving(host_app(SAMPLES)) as base:
        assert httpx2.get(f"{base}/health").status_code == 200


async def test_each_plugin_answers_at_its_own_path() -> None:
    """A plugin's folder name is its id and its path, a paid one's included."""
    with serving(host_app(SAMPLES)) as base:
        assert await tool_names(f"{base}/notes/mcp") == ["search"]
        assert await tool_names(f"{base}/paid/mcp") == ["scrape"]


async def test_without_proprietary_the_free_plugins_still_run(tmp_path: Path) -> None:
    """The open build: no Business Source License code, and nothing missing but it."""
    root = tmp_path / "plugins"
    shutil.copytree(SAMPLES, root)
    shutil.rmtree(root / "proprietary")

    with serving(host_app(root)) as base:
        assert await tool_names(f"{base}/notes/mcp") == ["search"]
        assert httpx2.post(f"{base}/paid/mcp").status_code == 404


async def test_a_folder_s_underscores_are_its_id_s_hyphens(tmp_path: Path) -> None:
    """A Python package cannot hold a hyphen, and a plugin's id cannot hold an underscore."""
    root = tmp_path / "plugins"
    shutil.copytree(SAMPLES / "notes", root / "google_search")

    with serving(host_app(root)) as base:
        assert await tool_names(f"{base}/google-search/mcp") == ["search"]
        assert httpx2.post(f"{base}/google_search/mcp").status_code == 404


async def test_a_plugin_that_fails_leaves_the_others_answering() -> None:
    with serving(host_app(SAMPLES)) as base:
        failed = await call(f"{base}/failing/mcp", "explode", {})
        found = await call(f"{base}/notes/mcp", "search", {"query": "x"})

    assert failed.is_error
    assert found.structured_content == {"result": "found x"}


@pytest.mark.parametrize(
    "folder",
    ["host", "mcp_server", "license_check", "scraping", "license", "admin", "api"],
)
def test_a_reserved_folder_is_never_a_plugin(tmp_path: Path, folder: str) -> None:
    """The host's own folders sit beside the plugins and must not be served."""
    root = tmp_path / "plugins"
    shutil.copytree(SAMPLES / "notes", root / folder)

    with serving(host_app(root)) as base:
        assert httpx2.post(f"{base}/{folder}/mcp").status_code == 404


async def test_without_a_paid_plugin_there_is_no_license_to_ask_about(
    tmp_path: Path,
) -> None:
    root = tmp_path / "plugins"
    shutil.copytree(SAMPLES, root)
    shutil.rmtree(root / "proprietary")
    with serving(host_app(root)) as base:
        assert httpx2.get(f"{base}/license").status_code == 404
