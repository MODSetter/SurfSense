"""What the app does on its own, in an interpreter conftest has not touched."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_every_relationship_resolves() -> None:
    """conftest imports every slice, so only a clean interpreter sees a missing one.

    Without that, a relationship naming its target as a string stays unresolved
    and each route touching that table returns 500 to a user, while the suite
    stays green.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sqlalchemy.orm import configure_mappers\n"
            "from api.main import create_app\n"
            "create_app()\n"
            "configure_mappers()\n",
        ],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
