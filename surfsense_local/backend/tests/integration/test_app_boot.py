"""What the app does on its own, in an interpreter conftest has not touched."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _boot(
    source: str, data_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if data_dir is not None:
        environment["SURFSENSE_LOCAL_DATA_DIR"] = str(data_dir)

    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_the_app_starts_on_a_machine_it_has_never_run_on(tmp_path: Path) -> None:
    """conftest makes its data directory before importing anything, a user does not.

    The queue opens its file as the module is imported, so a missing
    ~/.surfsense stopped the app at import with no route ever reached.
    """
    result = _boot(
        "from api.main import create_app\ncreate_app()\n", tmp_path / "never-created"
    )

    assert result.returncode == 0, result.stderr


def test_every_relationship_resolves() -> None:
    """conftest imports every feature, so only a clean interpreter sees a missing one.

    Without that, a relationship naming its target as a string stays unresolved
    and each route touching that table returns 500 to a user, while the suite
    stays green.
    """
    result = _boot(
        "from sqlalchemy.orm import configure_mappers\n"
        "from api.main import create_app\n"
        "create_app()\n"
        "configure_mappers()\n"
    )

    assert result.returncode == 0, result.stderr
