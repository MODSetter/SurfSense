"""The plugin the repository ships as its example, run the way the app runs any."""

import json
import shutil
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.tasks import run_plugin
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings

pytestmark = pytest.mark.integration

EXAMPLE = Path(__file__).resolve().parents[5] / "plugins" / "bundles" / "example"
VERSION = "2.0.3"


def install_the_example() -> None:
    """Put the example where install would: its files, its dependency, a stamped version."""
    storage = get_storage_settings()
    folder = storage.plugin_dir("example", VERSION)
    shutil.copytree(
        EXAMPLE, folder, ignore=shutil.ignore_patterns("dev-data", "__pycache__")
    )
    storage.plugin_data_dir("example").mkdir()
    manifest = json.loads((folder / "manifest.json").read_text())
    (folder / "manifest.json").write_text(json.dumps(manifest | {"version": VERSION}))


def test_the_example_counts_words_into_a_note(
    session: Session, running_app: str
) -> None:
    """The demo: the app runs the example as a process, and its note is in the workspace."""
    if not (EXAMPLE / "site-packages" / "tabulate").is_dir():
        pytest.skip(
            "the example's dependency is not installed; run"
            ' `surfsense-plugins invoke example count-words --input text="a b"` once'
        )
    install_the_example()
    workspace = Workspace(name="Plugins")
    session.add(workspace)
    session.flush()
    run = PluginRun(
        workspace_id=workspace.id,
        plugin_id="example",
        version=VERSION,
        action="count-words",
        inputs={"text": "the cat and the hat", "top": 1},
    )
    session.add(run)
    session.commit()

    run_plugin.call_local(run.id)

    session.refresh(run)
    session.commit()
    assert (run.status, run.error) == (PluginRunStatus.SUCCEEDED, None)
    documents = f"{running_app}/workspaces/{workspace.id}/documents"
    (listed,) = httpx.get(documents).json()
    note = httpx.get(f"{documents}/{listed['id']}").json()
    assert note["title"] == "Word count #1"
    assert note["content"] == (
        "the cat and the hat\n\n| Word   |   Count |\n|--------|---------|\n| the    |       2 |\n"
    )
