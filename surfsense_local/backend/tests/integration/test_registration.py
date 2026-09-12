"""import_models() and import_tasks() are hand-written lists that can fall
behind, and both do so quietly. These read the files off disk instead."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[2]


def on_disk(file_name: str) -> set[str]:
    """Every `modules/<feature>/<file_name>.py`, as an import name."""
    found = (BACKEND / "modules").glob(f"*/{file_name}.py")
    return {f"modules.{path.parent.name}.{file_name}" for path in found}


def imported_by(call: str) -> set[str]:
    """What the call pulls in, in an interpreter conftest has not touched."""
    result = subprocess.run(
        [sys.executable, "-c", f"{call}\nimport sys\nprint(*sys.modules)\n"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    return set(result.stdout.split())


def test_every_model_is_imported() -> None:
    """A model missing from the list reaches a user as a 500 from every route."""
    missing = on_disk("models") - imported_by(
        "from shared.db import import_models\nimport_models()"
    )

    assert not missing


def test_every_task_is_imported() -> None:
    """A task missing from the list is a job the worker silently throws away."""
    missing = on_disk("tasks") - imported_by(
        "from shared.queue import import_tasks\nimport_tasks()"
    )

    assert not missing
