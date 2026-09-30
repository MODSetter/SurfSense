"""The plugins worker as its own process, on the queue and database the API writes to."""

import os
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil
import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.tasks import run_plugin
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from shared.migrations import upgrade_to_head
from shared.queue import plugins_queue

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[3]
# The queue opens its file at import, so the worker has to be handed the same
# data directory conftest set before anything else was imported.
DATA_DIR = Path(os.environ["SURFSENSE_LOCAL_DATA_DIR"])

WAITS_ON_THE_NETWORK = """
import time

from surfsense_plugin_sdk import action


@action("go")
def go() -> None:
    time.sleep(3)
"""


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Engine:
    """The database in the directory the worker process reads, not this test's own.

    That directory is shared by the session, so each test starts it with no
    plugin installed and no run recorded.
    """
    monkeypatch.setattr(get_storage_settings(), "data_dir", DATA_DIR)
    shutil.rmtree(DATA_DIR / "plugins", ignore_errors=True)
    engine = create_db_engine(DATA_DIR / "surfsense.db")
    upgrade_to_head(engine)
    with engine.begin() as connection:
        connection.execute(delete(PluginRun))
    return engine


def start_worker() -> subprocess.Popen:
    """`worker.py plugins` in a process group of its own, as Electron starts it."""
    return subprocess.Popen(
        [sys.executable, "worker.py", "plugins"],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@pytest.fixture
def worker() -> Iterator[subprocess.Popen]:
    """A plugins worker for the length of one test."""
    process = start_worker()
    yield process
    process.terminate()
    process.wait(timeout=10)


def statuses(engine: Engine) -> Counter[PluginRunStatus]:
    """How many runs are in each status right now, read from the other process's work."""
    with create_session_factory(engine)() as session:
        return Counter(session.scalars(select(PluginRun.status)).all())


def wait_until(
    worker: subprocess.Popen, reached: Callable[[], bool], what: str
) -> None:
    """Block until the worker got there, or fail saying what never happened."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if reached():
            return
        assert worker.poll() is None, "the plugins worker stopped"
        time.sleep(0.1)
    raise AssertionError(f"the plugins worker never had {what}")


def test_the_plugins_worker_runs_four_at_a_time_and_the_fifth_waits(
    engine: Engine,
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
    worker: subprocess.Popen,
) -> None:
    """Plugin runs mostly wait on the network, so they overlap, up to a limit."""
    install(WAITS_ON_THE_NETWORK)
    for _ in range(5):
        run_plugin(queued_run().id)
    assert plugins_queue.pending_count() == 5, "the two processes share one queue file"

    wait_until(
        worker,
        lambda: statuses(engine)[PluginRunStatus.RUNNING] == 4,
        "four runs going",
    )
    assert statuses(engine)[PluginRunStatus.QUEUED] == 1

    wait_until(
        worker,
        lambda: statuses(engine)[PluginRunStatus.SUCCEEDED] == 5,
        "all five runs done",
    )


def test_a_run_the_app_quit_during_leaves_no_process_and_fails_as_interrupted(
    engine: Engine,
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """Quitting stops the worker's whole group, plugin included; the next start says so."""
    install(
        """
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
    )
    run = queued_run()
    run_plugin(run.id)
    first = start_worker()
    written = get_storage_settings().plugin_data_dir("fake") / "pids"
    wait_until(first, written.exists, "the plugin running")
    pids = [int(pid) for pid in written.read_text().split()]

    # What the app's supervisor does to a worker when the app quits.
    os.killpg(first.pid, signal.SIGKILL)
    first.wait(timeout=10)

    assert not [pid for pid in pids if not gone(pid)]
    assert statuses(engine) == Counter({PluginRunStatus.RUNNING: 1})
    second = start_worker()
    try:
        wait_until(
            second,
            lambda: statuses(engine)[PluginRunStatus.FAILED] == 1,
            "the interrupted run failed",
        )
    finally:
        second.terminate()
        second.wait(timeout=10)
    session.refresh(run)
    session.commit()
    assert run.error == "interrupted"


def gone(pid: int) -> bool:
    """A process that no longer runs, given a moment to be reaped."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.05)
    return False


def test_a_run_left_queued_by_the_last_session_does_not_start_by_itself(
    engine: Engine,
    session: Session,
    install: Callable[..., Path],
    queued_run: Callable[..., PluginRun],
) -> None:
    """The user asked for it before quitting; launching the app again is not asking twice."""
    install(
        """
from surfsense_plugin_sdk import action, data


@action("go")
def go() -> None:
    (data() / "started").write_text("yes")
"""
    )
    run = queued_run()
    run.created_at = datetime.now(UTC) - timedelta(hours=1)
    session.commit()
    run_plugin(run.id)

    worker = start_worker()
    try:
        wait_until(
            worker,
            lambda: statuses(engine)[PluginRunStatus.FAILED] == 1,
            "the queued run failed",
        )
        # Long enough for the worker to have taken the task, had it not been withdrawn.
        time.sleep(2)
    finally:
        worker.terminate()
        worker.wait(timeout=10)

    session.refresh(run)
    session.commit()
    assert (run.error, run.started_at) == ("interrupted", None)
    assert not (get_storage_settings().plugin_data_dir("fake") / "started").exists()
