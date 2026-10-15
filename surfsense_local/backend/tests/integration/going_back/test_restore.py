"""Restoring the copy taken before the update, when the undo steps are not there."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from shared.db import create_db_engine
from shared.going_back.newer_database import database_revision
from shared.going_back.restore import restore_backup
from shared.migrations import upgrade_to_head
from tests.integration.going_back.newer_app import (
    newer_head,
    open_with_newer_release,
    this_head,
)

pytestmark = pytest.mark.integration


def _library_a_newer_release_opened(data_dir: Path) -> Engine:
    engine = create_db_engine(data_dir / "surfsense.db")
    upgrade_to_head(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
    open_with_newer_release(engine, data_dir)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO workspaces(id, name) VALUES (2, 'Added later')")
        )
    return engine


def _workspaces(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return (
            connection.execute(text("SELECT name FROM workspaces ORDER BY id"))
            .scalars()
            .all()
        )


def test_the_database_becomes_the_copy_from_before_the_update(tmp_path: Path) -> None:
    """What was added since is gone from the app."""
    engine = _library_a_newer_release_opened(tmp_path)

    restore_backup(engine, tmp_path)

    assert database_revision(engine) == this_head()
    assert _workspaces(engine) == ["Notes"]


def test_what_was_added_since_is_set_aside_not_lost(tmp_path: Path) -> None:
    """The newer database survives beside the backups."""
    engine = _library_a_newer_release_opened(tmp_path)

    restore_backup(engine, tmp_path)

    [kept] = (tmp_path / "backups" / "set-aside").iterdir()
    copy = create_db_engine(kept)
    assert database_revision(copy) == newer_head()
    assert _workspaces(copy) == ["Notes", "Added later"]


def test_without_a_usable_copy_nothing_changes(tmp_path: Path) -> None:
    """Not even a set-aside copy is written."""
    engine = _library_a_newer_release_opened(tmp_path)
    for backup in (tmp_path / "backups").glob("*.db"):
        backup.unlink()

    with pytest.raises(LookupError):
        restore_backup(engine, tmp_path)

    assert database_revision(engine) == newer_head()
    assert _workspaces(engine) == ["Notes", "Added later"]
    assert not (tmp_path / "backups" / "set-aside").exists()
