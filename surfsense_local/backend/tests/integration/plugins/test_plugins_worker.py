"""The plugins worker as its own process, on the queue and database the API writes to."""

import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
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
    """The database in the directory the worker process reads, not this test's own."""
    monkeypatch.setattr(get_storage_settings(), "data_dir", DATA_DIR)
    engine = create_db_engine(DATA_DIR / "surfsense.db")
    upgrade_to_head(engine)
    return engine


@pytest.fixture
def worker() -> Iterator[subprocess.Popen]:
    """`worker.py plugins`, as Electron starts it."""
    process = subprocess.Popen(
        [sys.executable, "worker.py", "plugins"],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
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
