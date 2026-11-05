"""Tests run in parallel workers (`pytest -n`) share nothing they write."""

import os
from pathlib import Path

import pytest

from shared import queue

pytestmark = pytest.mark.unit


def test_each_worker_queues_jobs_in_its_own_file() -> None:
    """Every test empties the queue it enqueues to; a file another worker
    shares would lose that worker's jobs mid-test."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker is None:
        pytest.skip("not run in a parallel worker")

    assert worker in Path(queue.ingest_queue.storage.filename).parent.name
