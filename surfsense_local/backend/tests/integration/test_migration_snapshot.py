"""A copy of the user's database is written before any revision touches it."""

import os
import struct
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from alembic import command
from shared.db import create_db_engine
from shared.migrations import upgrade_to_head

pytestmark = pytest.mark.integration

_ALEMBIC = Path(__file__).parents[2] / "alembic"


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_ALEMBIC))
    config.attributes["engine"] = engine
    return config


def _head_and_previous() -> tuple[str, str]:
    config = Config()
    config.set_main_option("script_location", str(_ALEMBIC))
    head = ScriptDirectory.from_config(config).get_revision("head")
    assert isinstance(head.down_revision, str)
    return head.revision, head.down_revision


def _revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _populated_behind_head(path: Path) -> Engine:
    """A library with one indexed chunk, one revision short of head."""
    engine = create_db_engine(path)
    _, previous = _head_and_previous()
    command.upgrade(_config(engine), previous)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        connection.execute(
            text(
                "INSERT INTO documents(id, workspace_id, title, document_type, status) "
                "VALUES (1, 1, 'note', 'NOTE', 'ready')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chunks(id, document_id, position, content) "
                "VALUES (1, 1, 0, 'the ship sails at dawn')"
            )
        )
        connection.execute(
            text("INSERT INTO chunk_vectors(rowid, embedding) VALUES (1, :vector)"),
            {"vector": struct.pack("384f", *([0.1] * 384))},
        )
    return engine


def _counts(engine: Engine) -> tuple[int, int, int]:
    with engine.connect() as connection:
        return (
            connection.execute(text("SELECT count(*) FROM chunks")).scalar_one(),
            connection.execute(text("SELECT count(*) FROM chunk_vectors")).scalar_one(),
            connection.execute(
                text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'ship'")
            ).scalar_one(),
        )


def test_a_database_behind_head_is_copied_before_it_migrates(tmp_path: Path) -> None:
    """The copy holds the old schema and the same chunks, vectors and keyword index."""
    engine = _populated_behind_head(tmp_path / "surfsense.db")
    head, previous = _head_and_previous()
    backups = tmp_path / "backups"

    upgrade_to_head(engine, backups_dir=backups)

    snapshot = backups / f"{previous}-{head}.db"
    assert [path.name for path in backups.iterdir()] == [snapshot.name]
    copy = create_db_engine(snapshot)
    assert _revision(copy) == previous
    assert _counts(copy) == (1, 1, 1)
    assert _revision(engine) == head


def test_a_new_database_and_one_at_head_write_no_copy(tmp_path: Path) -> None:
    """Nothing to lose on a first start, and nothing changes at head."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    backups = tmp_path / "backups"

    upgrade_to_head(engine, backups_dir=backups)
    upgrade_to_head(engine, backups_dir=backups)

    assert not backups.exists() or list(backups.iterdir()) == []


def test_only_the_two_newest_copies_are_kept(tmp_path: Path) -> None:
    """Three upgrades leave the latest two snapshots."""
    backups = tmp_path / "backups"
    backups.mkdir()
    for index, name in enumerate(("0001-0002.db", "0002-0003.db")):
        stale = backups / name
        stale.write_bytes(b"old")
        # Older than anything the upgrade writes.
        os.utime(stale, (1_000_000 + index, 1_000_000 + index))
    engine = _populated_behind_head(tmp_path / "surfsense.db")
    head, previous = _head_and_previous()

    upgrade_to_head(engine, backups_dir=backups)

    assert sorted(path.name for path in backups.iterdir()) == sorted(
        ["0002-0003.db", f"{previous}-{head}.db"]
    )


def test_a_copy_that_cannot_be_written_stops_the_upgrade(tmp_path: Path) -> None:
    """No copy, no migration: the database stays at its revision and start fails."""
    engine = _populated_behind_head(tmp_path / "surfsense.db")
    _, previous = _head_and_previous()
    # A file where the folder should be: nothing can be written beneath it.
    blocked = tmp_path / "backups"
    blocked.write_bytes(b"not a folder")

    with pytest.raises(RuntimeError, match="snapshot"):
        upgrade_to_head(engine, backups_dir=blocked)

    assert _revision(engine) == previous


def test_a_cleanup_that_fails_too_still_reports_the_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Start is told the copy failed and why, whatever removing its partial file says.

    Beneath a file, macOS and Linux refuse the removal itself; Windows calls the
    partial file missing. This refusal is raised on all three.
    """
    engine = _populated_behind_head(tmp_path / "surfsense.db")
    _, previous = _head_and_previous()
    blocked = tmp_path / "backups"
    blocked.write_bytes(b"not a folder")
    unlink = Path.unlink

    def refuse_the_partial(path: Path, missing_ok: bool = False) -> None:
        if path.name.endswith(".partial"):
            raise NotADirectoryError(20, "Not a directory", str(path))
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse_the_partial)

    with pytest.raises(RuntimeError, match="snapshot") as raised:
        upgrade_to_head(engine, backups_dir=blocked)

    assert isinstance(raised.value.__cause__, FileExistsError)
    assert _revision(engine) == previous
