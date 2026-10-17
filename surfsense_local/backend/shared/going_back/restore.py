from pathlib import Path

from sqlalchemy import Engine

from shared.going_back.failure import GoingBackError
from shared.going_back.load_copy import load_copy
from shared.going_back.set_aside import set_aside
from shared.going_back.usable_backup import usable_backup


def restore_backup(engine: Engine, data_dir: Path) -> None:
    """Replace the database with the copy taken before the update.

    What was added since is lost from the app but kept in the set-aside copy.
    """
    backup = usable_backup(data_dir)
    if backup is None:
        raise LookupError("no copy in backups/ that this release can open")
    set_aside(engine, data_dir)
    try:
        load_copy(engine, backup)
    except Exception as error:
        # SQLite does not promise the live file is untouched after a failed backup step.
        raise GoingBackError(str(error), data_unchanged=False) from error
