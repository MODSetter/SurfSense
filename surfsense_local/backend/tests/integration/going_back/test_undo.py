"""Undoing a newer release's revisions keeps what the user added since."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

from shared.db import create_db_engine
from shared.going_back.failure import GoingBackError
from shared.going_back.newer_database import database_revision
from shared.going_back.undo import undo_newer_revisions
from shared.migrations import upgrade_to_head
from tests.integration.going_back.newer_app import (
    newer_head,
    open_with_newer_release,
    save_newer_scripts,
    this_head,
)

pytestmark = pytest.mark.integration


def _library_a_newer_release_opened(data_dir: Path) -> Engine:
    """One note from before the update and one added after it."""
    engine = create_db_engine(data_dir / "surfsense.db")
    upgrade_to_head(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        _add_note(connection, 1, "before the update")
    open_with_newer_release(engine, data_dir)
    with engine.begin() as connection:
        _add_note(connection, 2, "after the update")
    return engine


def _add_note(connection, document_id: int, title: str) -> None:
    connection.execute(
        text(
            "INSERT INTO documents(id, workspace_id, title, document_type, status) "
            "VALUES (:id, 1, :title, 'NOTE', 'ready')"
        ),
        {"id": document_id, "title": title},
    )


def _titles(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return (
            connection.execute(text("SELECT title FROM documents ORDER BY id"))
            .scalars()
            .all()
        )


def test_the_database_returns_to_this_release_with_everything_added_since(
    tmp_path: Path,
) -> None:
    """Only what the undo steps drop is lost; here, the newer release's own table."""
    engine = _library_a_newer_release_opened(tmp_path)

    undo_newer_revisions(engine, tmp_path)

    assert database_revision(engine) == this_head()
    assert _titles(engine) == ["before the update", "after the update"]
    assert not inspect(engine).has_table("newer_notes")


def test_the_newer_database_is_set_aside_first(tmp_path: Path) -> None:
    """Undo steps may drop what this release has no place for; the copy still has it."""
    engine = _library_a_newer_release_opened(tmp_path)

    undo_newer_revisions(engine, tmp_path)

    [kept] = (tmp_path / "backups" / "set-aside").iterdir()
    copy = create_db_engine(kept)
    assert database_revision(copy) == newer_head()
    assert _titles(copy) == ["before the update", "after the update"]


def test_an_undo_step_that_fails_leaves_the_database_as_it_was(tmp_path: Path) -> None:
    """The later revision has already undone, so only the set-aside copy restores it."""
    engine = _library_a_newer_release_opened(tmp_path)
    save_newer_scripts(tmp_path / "migrations", first_undo_fails=True)

    with pytest.raises(GoingBackError) as failed:
        undo_newer_revisions(engine, tmp_path)

    assert failed.value.data_unchanged
    assert database_revision(engine) == newer_head()
    assert inspect(engine).has_table("newer_notes")
    assert _titles(engine) == ["before the update", "after the update"]


def test_an_undo_whose_copy_cannot_be_loaded_back_says_the_data_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dialog must not tell the user their data is as the newer version left it."""
    engine = _library_a_newer_release_opened(tmp_path)
    save_newer_scripts(tmp_path / "migrations", first_undo_fails=True)

    def disk_is_full(_engine: Engine, _copy: Path) -> None:
        raise OSError("database or disk is full")

    monkeypatch.setattr("shared.going_back.undo.load_copy", disk_is_full)

    with pytest.raises(GoingBackError) as failed:
        undo_newer_revisions(engine, tmp_path)

    assert not failed.value.data_unchanged
    # The log must say why it failed and where the full copy is.
    [kept] = (tmp_path / "backups" / "set-aside").iterdir()
    assert "undo broke" in str(failed.value)
    assert str(kept) in str(failed.value)
