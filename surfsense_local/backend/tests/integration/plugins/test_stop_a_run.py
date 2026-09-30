"""A run the plugin does not end itself: cancelled, or out of time."""

import threading
import time
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.cancel_run import cancel_plugin_run
from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.tasks import run_plugin
from shared.config import get_storage_settings
from shared.queue import plugins_queue

pytestmark = pytest.mark.integration

# Starts a process of its own, then waits: both pids land in its data folder.
WAITS_WITH_A_CHILD = """
import os
import subprocess
import sys
import time

from surfsense_plugin_sdk import action, data


@action("go")
def go() -> None:
    child = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(60)"])
    (data() / "pids").write_text(f"{os.getpid()} {child.pid}")
    time.sleep(60)
"""


def in_the_background(run: PluginRun) -> threading.Thread:
    """The worker's thread carrying out the run, while the test acts on it."""
    thread = threading.Thread(target=run_plugin.call_local, args=(run.id,))
    thread.start()
    return thread


def pids_once_running() -> list[int]:
    """The plugin's pid and its child's, once the plugin has written them."""
    written = get_storage_settings().plugin_data_dir("fake") / "pids"
    deadline = time.monotonic() + 15
    while not written.exists():
        assert time.monotonic() < deadline, "the plugin never started"
        time.sleep(0.05)
    return [int(pid) for pid in written.read_text().split()]


def gone(pid: int) -> bool:
    """A process that no longer runs; a zombie is waiting only to be reaped."""
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def test_a_cancelled_run_stops_the_plugin_and_what_it_started(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Cancel reaches every process of the run, not only the one the app started."""
    install(WAITS_WITH_A_CHILD)
    run = queued_run()
    worker = in_the_background(run)
    pids = pids_once_running()

    assert cancel_plugin_run(session, run)
    worker.join(timeout=10)

    assert not worker.is_alive()
    session.refresh(run)
    session.commit()
    assert run.status is PluginRunStatus.CANCELLED
    assert run.finished_at is not None
    assert all(gone(pid) for pid in pids)


def test_a_run_out_of_time_is_stopped_and_fails_with_timeout(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The action's own timeout_seconds, not the app's default, bounds the run."""
    install(WAITS_WITH_A_CHILD, timeout_seconds=2)
    run = queued_run()
    began = time.monotonic()

    run_plugin.call_local(run.id)

    assert time.monotonic() - began < 8
    session.refresh(run)
    session.commit()
    assert (run.status, run.error) == (PluginRunStatus.FAILED, "timeout")
    assert all(gone(pid) for pid in pids_once_running())


def test_a_plugin_that_ignores_being_asked_to_stop_is_killed(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Asked first, so a plugin can tidy up; killed five seconds later regardless."""
    install(
        """
import signal
import time

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)
""",
        timeout_seconds=1,
    )
    run = queued_run()
    began = time.monotonic()

    run_plugin.call_local(run.id)

    assert 5 <= time.monotonic() - began < 12
    session.refresh(run)
    session.commit()
    assert (run.status, run.error) == (PluginRunStatus.FAILED, "timeout")


def test_a_run_cancelled_while_queued_never_starts(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Its queued task is withdrawn, and a copy that still arrives does nothing."""
    install(
        """
from surfsense_plugin_sdk import action, data


@action("go")
def go() -> None:
    (data() / "started").write_text("yes")
"""
    )
    run = queued_run()
    run_plugin(run.id)
    (task,) = plugins_queue.pending()

    assert cancel_plugin_run(session, run)
    run_plugin.call_local(run.id)

    assert plugins_queue.is_revoked(task)
    session.refresh(run)
    session.commit()
    assert run.status is PluginRunStatus.CANCELLED
    assert run.started_at is None
    assert not (get_storage_settings().plugin_data_dir("fake") / "started").exists()


def test_a_run_that_already_ended_cannot_be_cancelled(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Cancel says so, so the caller can tell the user nothing was running."""
    install(
        """
from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    pass
"""
    )
    run = queued_run()
    run_plugin.call_local(run.id)
    session.refresh(run)

    assert not cancel_plugin_run(session, run)
    assert run.status is PluginRunStatus.SUCCEEDED


def test_a_process_the_plugin_leaves_behind_does_not_hold_its_run_open(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """It shares the plugin's output, which would otherwise never close."""
    install(
        """
import subprocess
import sys

from surfsense_plugin_sdk import action, data


@action("go")
def go() -> None:
    left = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(30)"])
    (data() / "pids").write_text(str(left.pid))
    print("done")
"""
    )
    run = queued_run()
    began = time.monotonic()

    try:
        run_plugin.call_local(run.id)
        assert time.monotonic() - began < 10
        session.refresh(run)
        session.commit()
        assert (run.status, run.log_tail) == (PluginRunStatus.SUCCEEDED, "done\n")
    finally:
        (left,) = pids_once_running()
        psutil.Process(left).kill()


async def test_deleting_a_workspace_stops_its_runs_before_anything_goes(
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    client: AsyncClient,
) -> None:
    """A plugin still writing to a deleted workspace would fail for no fault of its own."""
    install(WAITS_WITH_A_CHILD)
    run = queued_run()
    worker = in_the_background(run)
    pids = pids_once_running()

    reply = await client.delete(f"/workspaces/{run.workspace_id}")

    assert reply.status_code == 204
    assert all(gone(pid) for pid in pids)
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert not session.scalars(select(PluginRun).where(PluginRun.id == run.id)).all()
    session.commit()


async def test_a_run_no_worker_is_carrying_out_does_not_keep_its_workspace(
    session: Session,
    queued_run: Callable[..., PluginRun],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Left running by a worker that is gone: its plugin went with it, so the wait ends."""
    monkeypatch.setattr("modules.plugins.stop_workspace_runs.STOP_WAIT_SECONDS", 1)
    run = queued_run()
    run.status = PluginRunStatus.RUNNING
    session.commit()

    reply = await client.delete(f"/workspaces/{run.workspace_id}")

    assert reply.status_code == 204
    assert not session.scalars(select(PluginRun).where(PluginRun.id == run.id)).all()
    session.commit()
