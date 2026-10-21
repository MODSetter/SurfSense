from pathlib import Path

from sqlalchemy import Engine

from alembic import command
from shared.going_back.data_folder import migrations_dir
from shared.going_back.failure import GoingBackError
from shared.going_back.load_copy import load_copy
from shared.going_back.saved_migrations import with_saved_migrations
from shared.going_back.set_aside import set_aside
from shared.going_back.this_release import this_release_head


def undo_newer_revisions(engine: Engine, data_dir: Path) -> None:
    """Run the newer release's saved undo steps back to this release's head.

    Each revision commits on its own, so a failure partway would strand the
    database between two revisions; the set-aside copy is loaded back instead.
    """
    newer = set_aside(engine, data_dir)
    try:
        with with_saved_migrations(migrations_dir(data_dir)) as config:
            config.attributes["engine"] = engine
            # Not "head": with the saved scripts loaded, that is the newer release's.
            command.downgrade(config, this_release_head())
    except Exception as error:
        try:
            load_copy(engine, newer)
        except Exception as load_error:
            raise GoingBackError(
                f"{error}; loading the set-aside copy back failed too: {load_error}. "
                f"The full copy from before going back is {newer}",
                data_unchanged=False,
            ) from error
        raise GoingBackError(str(error), data_unchanged=True) from error
