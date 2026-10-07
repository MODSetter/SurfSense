"""The sweep's files, rewritten whole while `report` may be reading them."""

import json
import os
import threading
from pathlib import Path

import pytest

from tests.live.sweep.results import write_atomic

pytestmark = pytest.mark.unit


@pytest.mark.skipif(
    os.name != "nt", reason="only Windows refuses to replace an open file"
)
def test_a_rewrite_waits_out_a_reader_instead_of_stopping_the_runner(
    tmp_path: Path,
) -> None:
    """`report` holding sweep-results.json open for a moment must not crash the runner mid-sweep."""
    path = tmp_path / "sweep-results.json"
    write_atomic(path, {"spent": 1.0})
    reader = path.open("rb")
    threading.Timer(0.1, reader.close).start()

    write_atomic(path, {"spent": 2.0})

    assert json.loads(path.read_text(encoding="utf-8")) == {"spent": 2.0}
