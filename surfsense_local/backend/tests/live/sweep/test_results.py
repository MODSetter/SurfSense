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


def test_a_model_capped_on_a_case_is_listed_as_assumed_not_measured(tmp_path) -> None:
    """The catalog gets it with the assumed flagships, with the reason, never as a 0 of 2 row."""
    import json

    from tests.live.sweep.attempt import Attempt
    from tests.live.sweep.model_list import select
    from tests.live.sweep.results import RESULTS, write

    listing = {
        "data": [
            {
                "id": "openai/gpt-6-sol",
                "context_length": 400_000,
                "supported_parameters": ["tools"],
                "pricing": {"prompt": "0.000002", "completion": "0.00001"},
                "architecture": {"input_modalities": ["text"]},
            }
        ]
    }
    (model,) = select(listing, set()).sweep
    attempts = [
        Attempt(model.id, "smoke", 1, "passed", cost=0.01, ended=1.0),
        Attempt(
            model.id, "pdf-brief", 1, "failed", kind="case-cap", cost=3.02, ended=2.0
        ),
    ]

    write(tmp_path, [model], attempts, [], {}, listing)

    written = json.loads((tmp_path / RESULTS).read_text(encoding="utf-8"))
    assert written["models"] == []
    (assumed,) = written["assumed"]
    assert (assumed["id"], assumed["level"], assumed["assumed"]) == (
        model.id,
        "agent",
        True,
    )
    assert "dollar cap" in assumed["notes"][0]
