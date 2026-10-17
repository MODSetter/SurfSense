"""This release notices a database a newer release upgraded, and what it can do about it."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine

from alembic import command
from shared.db import create_db_engine
from shared.going_back.newer_database import going_back_options, is_newer_than_this_app
from shared.going_back.undo import undo_newer_revisions
from shared.migration_snapshot import snapshot_before_upgrade
from shared.migrations import upgrade_to_head
from tests.integration.going_back.newer_app import (
    ALEMBIC,
    newer_head,
    open_with_newer_release,
    previous_revision,
    this_head,
)

pytestmark = pytest.mark.integration


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    config.attributes["engine"] = engine
    return config


def test_a_database_a_newer_release_upgraded_is_newer(tmp_path: Path) -> None:
    """Its revision is one this release has never seen."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    upgrade_to_head(engine)
    open_with_newer_release(engine, tmp_path)

    assert is_newer_than_this_app(engine)


def test_a_new_database_and_one_at_head_are_not(tmp_path: Path) -> None:
    """Neither may trigger going back."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    assert not is_newer_than_this_app(engine)

    upgrade_to_head(engine)
    assert not is_newer_than_this_app(engine)


def _newer_library(data_dir: Path) -> Engine:
    engine = create_db_engine(data_dir / "surfsense.db")
    upgrade_to_head(engine)
    open_with_newer_release(engine, data_dir)
    return engine


def test_it_can_undo_with_the_scripts_the_newer_release_saved(tmp_path: Path) -> None:
    """They reach from the database's revision back to this release."""
    engine = _newer_library(tmp_path)

    assert going_back_options(engine, tmp_path).can_undo


def test_it_cannot_undo_without_them(tmp_path: Path) -> None:
    """A release before this one saved none."""
    engine = _newer_library(tmp_path)
    shutil.rmtree(tmp_path / "migrations")

    assert not going_back_options(engine, tmp_path).can_undo


def test_it_cannot_undo_when_a_saved_script_will_not_load(tmp_path: Path) -> None:
    """A script importing what this release lacks must not crash the start."""
    engine = _newer_library(tmp_path)
    script = next((tmp_path / "migrations").glob(f"{newer_head()}_*.py"))
    script.write_text("import module_this_release_lacks\n", encoding="utf-8")

    assert not going_back_options(engine, tmp_path).can_undo


def test_it_offers_the_copy_the_newer_release_saved_before_upgrading(
    tmp_path: Path,
) -> None:
    """It holds this release's head, so nothing has to migrate after it."""
    engine = _newer_library(tmp_path)

    backup = going_back_options(engine, tmp_path).backup

    assert backup == tmp_path / "backups" / f"{this_head()}-{newer_head()}.db"


def test_it_offers_no_copy_it_cannot_open(tmp_path: Path) -> None:
    """A copy taken between two later releases holds a revision this one lacks."""
    engine = _newer_library(tmp_path)
    (tmp_path / "backups" / f"{this_head()}-{newer_head()}.db").unlink()
    snapshot_before_upgrade(engine, tmp_path / "backups", newer_head(), "9999")

    assert going_back_options(engine, tmp_path).backup is None


def test_it_prefers_the_copy_at_its_own_revision(tmp_path: Path) -> None:
    """An older copy would also open, but would lose more."""
    engine = _newer_library(tmp_path)
    older = create_db_engine(tmp_path / "older.db")
    command.upgrade(_config(older), previous_revision())
    snapshot_before_upgrade(
        older, tmp_path / "backups", previous_revision(), this_head()
    )

    backup = going_back_options(engine, tmp_path).backup

    assert backup == tmp_path / "backups" / f"{this_head()}-{newer_head()}.db"


def _plant_a_script_that_leaves_a_mark(data_dir: Path, name: str) -> Path:
    mark = data_dir / f"{name}.ran"
    (data_dir / "migrations" / f"{name}.py").write_text(
        f"from pathlib import Path\nPath({str(mark)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    return mark


def test_the_options_run_no_saved_script(tmp_path: Path) -> None:
    """Nothing from the data folder runs before the user chooses to undo."""
    engine = _newer_library(tmp_path)
    marks = [
        _plant_a_script_that_leaves_a_mark(tmp_path, f"{newer_head()}_newer_pins"),
        _plant_a_script_that_leaves_a_mark(tmp_path, "zz_not_a_migration"),
    ]
    # The planted 0032 replaces the real one, so put its revision lines back after the mark.
    (tmp_path / "migrations" / f"{newer_head()}_newer_pins.py").write_text(
        (tmp_path / "migrations" / f"{newer_head()}_newer_pins.py").read_text()
        + f'revision = "{newer_head()}"\ndown_revision = "{int(newer_head()) - 1:04d}"\n',
        encoding="utf-8",
    )

    going_back_options(engine, tmp_path)

    assert [mark for mark in marks if mark.exists()] == []


def test_a_file_not_named_like_a_migration_is_never_run(tmp_path: Path) -> None:
    """Undo loads only NNNN_*.py, so a stray script in the folder stays inert."""
    engine = _newer_library(tmp_path)
    mark = _plant_a_script_that_leaves_a_mark(tmp_path, "zz_not_a_migration")

    assert going_back_options(engine, tmp_path).can_undo
    undo_newer_revisions(engine, tmp_path)

    assert not mark.exists()


def test_it_offers_no_copy_that_fails_its_integrity_check(tmp_path: Path) -> None:
    """A damaged copy would replace the user's database with a broken one."""
    engine = _newer_library(tmp_path)
    backup = tmp_path / "backups" / f"{this_head()}-{newer_head()}.db"
    with closing(sqlite3.connect(backup)) as copy:
        size = copy.execute("PRAGMA page_size").fetchone()[0]
        (page,) = copy.execute(
            "SELECT rootpage FROM sqlite_master WHERE name = 'workspaces'"
        ).fetchone()
    with backup.open("r+b") as raw:
        raw.seek((page - 1) * size)
        raw.write(b"\xff" * size)
    with closing(sqlite3.connect(backup)) as copy:
        # Still names its revision, so only the check can tell it is damaged.
        assert copy.execute("SELECT version_num FROM alembic_version").fetchone() == (
            this_head(),
        )

    assert going_back_options(engine, tmp_path).backup is None
