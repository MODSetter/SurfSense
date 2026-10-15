from dataclasses import dataclass
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import Engine

from shared.going_back.data_folder import migrations_dir
from shared.going_back.saved_migrations import with_saved_migrations
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
    """Whether the saved scripts reach from the database back to this release."""
    current = database_revision(engine)
    if current is None:
        return False
    with with_saved_migrations(migrations_dir(data_dir)) as config:
        try:
            scripts = ScriptDirectory.from_config(config)
            list(scripts.iterate_revisions(current, this_release_head()))
        # Anything a saved script raises as it loads: it was written for code this
        # release may not have.
        except Exception:
            return False
    return True


def _knows(scripts: ScriptDirectory, revision: str) -> bool:
    try:
        return scripts.get_revision(revision) is not None
    except CommandError:
        return False
