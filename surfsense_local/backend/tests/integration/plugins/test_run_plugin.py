"""One run of a plugin, as the worker carries it out: its own process, then the row."""

import json
import os
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.tasks import run_plugin

pytestmark = pytest.mark.integration


def reread(session: Session, run: PluginRun) -> None:
    """Load what the job recorded, and let go of the write lock reading took."""
    session.refresh(run)
    session.commit()


QUIET = """
from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    print("counted 3 words")
"""


def test_a_plugin_that_ends_cleanly_leaves_its_run_succeeded(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Exit 0 is the only thing the app reads as success."""
    install(QUIET)
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert run.status is PluginRunStatus.SUCCEEDED
    assert run.error is None
    assert run.log_tail == "counted 3 words\n"
    assert run.started_at is not None
    assert run.finished_at is not None


def test_a_plugin_that_exits_with_an_error_leaves_its_run_failed(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The reason is the plugin's to print; the app records the code and the log."""
    install(
        """
import sys

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    sys.exit("Token expired")
"""
    )
    run = queued_run()

    # Returning at all is the point: the worker outlives a plugin that fails.
    run_plugin.call_local(run.id)

    reread(session, run)
    assert run.status is PluginRunStatus.FAILED
    assert run.error == "exit 1"
    assert run.log_tail == "Token expired\n"
    assert run.finished_at is not None


PRINTS_ITS_ENVIRONMENT = """
import os

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    for name in sorted(os.environ):
        print(name)
"""


def test_nothing_of_the_apps_own_environment_reaches_a_plugin(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker holds the key to every stored API key; a plugin never gets it."""
    monkeypatch.setenv("SURFSENSE_LOCAL_SECRET", "the-key-to-every-stored-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "something-of-the-users")
    install(PRINTS_ITS_ENVIRONMENT)
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    names = run.log_tail.split()
    assert not [name for name in names if name.startswith("SURFSENSE_LOCAL_")]
    assert "AWS_SECRET_ACCESS_KEY" not in names
    assert "PATH" in names


def test_a_note_a_plugin_adds_is_in_the_runs_workspace_and_names_the_run(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    running_app: str,
) -> None:
    """The plugin writes through the app's own API while it runs; nothing is imported after."""
    install(
        """
from surfsense_plugin_sdk import action, document


@action("go")
def go() -> None:
    document.add(title="From a plugin", content="hi")
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert run.log_tail == ""
    assert run.status is PluginRunStatus.SUCCEEDED
    documents = f"{running_app}/workspaces/{run.workspace_id}/documents"
    (listed,) = httpx.get(documents).json()
    note = httpx.get(f"{documents}/{listed['id']}").json()
    assert (note["title"], note["content"]) == ("From a plugin", "hi")
    assert note["document_metadata"] == {
        "plugin_id": "fake",
        "plugin_version": "2.0.3",
        "action": "go",
        "run_id": run.id,
    }


def test_what_a_plugin_wrote_before_it_crashed_stays(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    running_app: str,
) -> None:
    """Each write was committed when its call returned; a failed run undoes none."""
    install(
        """
from surfsense_plugin_sdk import action, document


@action("go")
def go() -> None:
    document.add(title="First", content="one")
    document.add(title="Second", content="two")
    raise RuntimeError("the third page would not load")
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert (run.status, run.error) == (PluginRunStatus.FAILED, "exit 1")
    assert "the third page would not load" in run.log_tail
    listed = httpx.get(f"{running_app}/workspaces/{run.workspace_id}/documents").json()
    assert sorted(document["title"] for document in listed) == ["First", "Second"]


def test_a_worker_with_no_api_address_lets_the_sdk_say_so(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guessed port would fail as a refused connection, which explains nothing."""
    monkeypatch.delenv("SURFSENSE_LOCAL_PORT", raising=False)
    install(
        """
from surfsense_plugin_sdk import action, document


@action("go")
def go() -> None:
    document.add(title="Unreachable", content="x")
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert run.status is PluginRunStatus.FAILED
    assert "SURFSENSE_PLUGIN_API_URL is not set" in run.log_tail


def test_a_plugins_own_json_module_does_not_replace_pythons(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The SDK reads the inputs with `json`; a plugin's file of that name must not be it."""
    install(QUIET, **{"json.py": "raise SystemExit('the plugin file was imported')"})
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert (run.status, run.log_tail) == (
        PluginRunStatus.SUCCEEDED,
        "counted 3 words\n",
    )


def test_a_plugin_runs_in_a_process_of_its_own(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Never imported into the worker, so its crash or its imports cannot touch it."""
    install(
        """
import os

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    print(os.getpid())
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert int(run.log_tail) != os.getpid()


def test_a_plugin_gets_the_runs_inputs_and_their_file_is_gone_afterwards(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The inputs file is the run's own, and no run leaves one behind."""
    folder = install(
        """
import sys

from surfsense_plugin_sdk import action


@action("go")
def go(text: str, top: float | None) -> None:
    print(text, top, sys.argv[sys.argv.index("--inputs") + 1])
"""
    )
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["actions"][0]["inputs"] = [{"name": "text"}, {"name": "top"}]
    (folder / "manifest.json").write_text(json.dumps(manifest))
    run = queued_run(text="hello")

    run_plugin.call_local(run.id)

    reread(session, run)
    text, top, inputs_file = run.log_tail.split()
    assert (text, top) == ("hello", "None")
    assert not Path(inputs_file).parent.exists()


def test_only_the_last_of_a_long_log_is_kept(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """A plugin explains a failure last, so the end of the log is the part to keep."""
    install(
        """
from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    for line in range(4000):
        print(f"line {line:04}")
    print("the reason it failed")
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert len(run.log_tail.encode()) == 16 * 1024
    assert run.log_tail.endswith("line 3999\nthe reason it failed\n")


def test_a_plugin_cannot_import_what_the_app_has_installed(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The packaged app's plugin Python has nothing installed, so development must not either."""
    install(
        """
import importlib.util

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    print(importlib.util.find_spec("httpx") is None)
"""
    )
    run = queued_run()

    run_plugin.call_local(run.id)

    reread(session, run)
    assert (run.status, run.log_tail) == (PluginRunStatus.SUCCEEDED, "True\n")
