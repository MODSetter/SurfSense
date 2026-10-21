from dataclasses import dataclass
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import Engine

from shared.going_back.data_folder import migrations_dir
from shared.going_back.saved_scripts import read_saved_scripts
from shared.going_back.this_release import this_release_head, this_release_scripts
from shared.going_back.usable_backup import usable_backup


@dataclass(frozen=True)
class GoingBackOptions:
    can_undo: bool
    backup: Path | None


def is_newer_than_this_app(engine: Engine) -> bool:
    """Whether a later release migrated this database past anything this one knows."""
    current = database_revision(engine)
    return current is not None and not _knows(this_release_scripts(), current)


def going_back_options(engine: Engine, data_dir: Path) -> GoingBackOptions:
    return GoingBackOptions(
        can_undo=_can_undo(engine, data_dir), backup=usable_backup(data_dir)
    )


def database_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _can_undo(engine: Engine, data_dir: Path) -> bool:
    """Whether saved scripts lead from the database back to this release's head.

    Read from their source: nothing in the data folder runs before the user
    chooses to undo.
    """
    scripts = read_saved_scripts(migrations_dir(data_dir))
    head = this_release_head()
    revision = database_revision(engine)
    seen = set()
    while revision != head:
        script = scripts.get(revision) if revision else None
        if script is None or not script.stand_alone or revision in seen:
            return False
        seen.add(revision)
        revision = script.down_revision
    return True


def _knows(scripts: ScriptDirectory, revision: str) -> bool:
    try:
        return scripts.get_revision(revision) is not None
    except CommandError:
        return False
