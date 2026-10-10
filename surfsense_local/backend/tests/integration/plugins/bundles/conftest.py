import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.plugins.bundles.models import PluginRun
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory

PLUGIN_ID = "fake"
VERSION = "2.0.3"
ACTION = "go"


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the run opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def running_app(base_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """The real API over TCP, at the address Electron would hand the worker."""
    host, port = base_url.removeprefix("http://").split(":")
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", host)
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", port)
    return base_url


@pytest.fixture
def install() -> Callable[..., Path]:
    """Puts a one-action plugin where install would, and returns its folder."""

    def put(main: str, timeout_seconds: int | None = None, **other_files: str) -> Path:
        storage = get_storage_settings()
        folder = storage.plugin_dir(PLUGIN_ID, VERSION)
        folder.mkdir(parents=True)
        storage.plugin_data_dir(PLUGIN_ID).mkdir()
        manifest = {
            "id": PLUGIN_ID,
            "version": VERSION,
            "name": "Fake",
            "description": "A plugin written by a test.",
            "author": "Tests",
            "access": "free",
            "hosts": [],
            "actions": [{"name": ACTION, "title": "Go", "inputs": []}],
        }
        if timeout_seconds is not None:
            manifest["actions"][0]["timeout_seconds"] = timeout_seconds
        (folder / "manifest.json").write_text(json.dumps(manifest))
        (folder / "main.py").write_text(main)
        for name, content in other_files.items():
            (folder / name).write_text(content)
        return folder

    return put


@pytest.fixture
def queued_run(session: Session) -> Callable[..., PluginRun]:
    """Leaves a run of the fake plugin's action as the API would: queued."""

    def queue(**inputs: object) -> PluginRun:
        workspace = Workspace(name="Plugins")
        session.add(workspace)
        session.flush()
        run = PluginRun(
            workspace_id=workspace.id,
            plugin_id=PLUGIN_ID,
            version=VERSION,
            action=ACTION,
            inputs=inputs,
        )
        session.add(run)
        session.commit()
        return run

    return queue
