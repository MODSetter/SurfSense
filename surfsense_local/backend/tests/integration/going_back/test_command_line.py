"""What Electron runs: the API refusing a newer database, then the two going-back commands."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from shared.db import create_db_engine
from shared.going_back.exit_code import NEWER_DATABASE
from shared.going_back.newer_database import database_revision
from shared.migrations import upgrade_to_head
from tests.integration.going_back.newer_app import (
    newer_head,
    open_with_newer_release,
    this_head,
)

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).parents[3]


def _newer_library(data_dir: Path) -> Path:
    engine = create_db_engine(data_dir / "surfsense.db")
    upgrade_to_head(engine)
    open_with_newer_release(engine, data_dir)
    engine.dispose()
    return data_dir / "surfsense.db"


def _run(data_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, SURFSENSE_LOCAL_DATA_DIR=str(data_dir))
    environment["SURFSENSE_LOCAL_PORT"] = "0"
    return subprocess.run(
        [sys.executable, "main.py", *arguments],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )


def test_the_api_refuses_a_newer_database_and_leaves_it_alone(tmp_path: Path) -> None:
    """Electron reads the exit code; migrating would fail on revisions it lacks."""
    database = _newer_library(tmp_path)

    result = _run(tmp_path)

    assert result.returncode == NEWER_DATABASE, result.stderr
    assert database_revision(create_db_engine(database)) == newer_head()


def test_the_options_say_what_going_back_can_do(tmp_path: Path) -> None:
    """The dialog offers the undo, and dates the backup for the fallback."""
    _newer_library(tmp_path)

    result = _run(tmp_path, "--going-back-options")

    assert result.returncode == 0, result.stderr
    options = json.loads(result.stdout)
    assert options["can_undo"] is True
    assert datetime.fromisoformat(options["backup_saved_at"]).tzinfo is not None


@pytest.mark.parametrize("way", ["undo", "restore"])
def test_going_back_leaves_a_database_this_release_opens(
    tmp_path: Path, way: str
) -> None:
    """Either way, the next start finds a database at this release's head."""
    database = _newer_library(tmp_path)

    result = _run(tmp_path, "--go-back", way)

    assert result.returncode == 0, result.stderr
    assert database_revision(create_db_engine(database)) == this_head()


def test_going_back_that_fails_says_why(tmp_path: Path) -> None:
    """The reason reaches the session log; the dialog only says it failed."""
    _newer_library(tmp_path)
    for backup in (tmp_path / "backups").glob("*.db"):
        backup.unlink()

    result = _run(tmp_path, "--go-back", "restore")

    assert result.returncode == 1
    assert "no copy" in result.stderr
