"""The frozen worker ships the documents helper as a file, which every run folder copies."""

from pathlib import Path

import pytest

from worker.document_script.run_folder import HELPER

pytestmark = pytest.mark.unit

BUNDLING = Path(__file__).resolve().parents[3] / "bundling"


def test_the_worker_bundles_the_helper_where_the_run_folder_copies_it_from() -> None:
    """Bytecode alone would not do: the run folder copies the source by path, and
    without it every document render in the packaged app fails."""
    inputs = (BUNDLING / "worker_inputs.py").read_text(encoding="utf-8")

    assert HELPER.is_file()
    assert '"worker" / "document_script" / "surfsense_docs.py"' in inputs
    assert HELPER.parent.as_posix().endswith("worker/document_script")
