import subprocess
import sys
import time
from pathlib import Path

import pytest
from huey.api import Result
from huey.exceptions import TaskException

from modules.documents.tasks import ingest_document
from shared.queue import huey

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[3]


def wait_for_the_worker_to_run(result: Result) -> TaskException:
    """Block until the job's outcome lands in the result store."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            result.get()
        except TaskException as failure:
            return failure
        time.sleep(0.1)

    raise AssertionError("the worker never ran the job")


def test_the_consumer_runs_a_job_the_api_enqueued() -> None:
    """A started worker picks up work the upload route left on the queue."""
    result = ingest_document(1)
    assert huey.pending_count() == 1, "the two processes share one queue file"

    worker = subprocess.Popen(
        [sys.executable, "worker.py"],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        failure = wait_for_the_worker_to_run(result)
    finally:
        worker.terminate()
        worker.wait(timeout=10)

    # The stub's own message: it ran in the other process, which is the point.
    assert "worker/02-ingest.md" in str(failure)
