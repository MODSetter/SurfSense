import sqlite3
from contextlib import closing
from pathlib import Path

from shared.going_back.data_folder import backups_dir
from shared.going_back.this_release import this_release_scripts


def usable_backup(data_dir: Path) -> Path | None:
    """The undamaged copy in backups/ this release can open that loses the least.

    Judged by the revision inside the file, not its name. The latest revision
    this release knows wins, then the newest file.
    """
    order = {
        script.revision: position
        for position, script in enumerate(
            reversed(list(this_release_scripts().walk_revisions()))
        )
    }
    candidates = [
        (order[revision], backup.stat().st_mtime, backup)
        for backup in backups_dir(data_dir).glob("*.db")
        if (revision := _revision_inside(backup)) in order
    ]
    return max(candidates)[2] if candidates else None


def _revision_inside(backup: Path) -> str | None:
    try:
        uri = f"{backup.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            row = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            # A copy that opens can still be damaged; restoring it would replace
            # the user's database with a broken one.
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                return None
    except sqlite3.Error:
        return None  # Unreadable or not a database: not something to restore.
    return row[0] if row else None
