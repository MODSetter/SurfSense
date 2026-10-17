import json
import sys
from datetime import UTC, datetime

from shared.config import get_storage_settings
from shared.db import create_db_engine
from shared.going_back.exit_code import NEWER_DATABASE
from shared.going_back.newer_database import going_back_options, is_newer_than_this_app
from shared.going_back.restore import restore_backup
from shared.going_back.undo import undo_newer_revisions


def refuse_a_newer_database() -> None:
    """Exit before serving when a later release upgraded the database.

    Its revisions are unknown here, so migrating would fail anyway; this exit
    tells Electron why instead of a crash.
    """
    database = get_storage_settings().database_path
    if not database.exists():
        return
    engine = create_db_engine(database)
    try:
        newer = is_newer_than_this_app(engine)
    finally:
        engine.dispose()
    if newer:
        sys.stderr.write("the database was upgraded by a newer release of SurfSense\n")
        sys.exit(NEWER_DATABASE)


def print_options() -> int:
    """Print what going back can do, as JSON, for Electron's dialog."""
    storage = get_storage_settings()
    engine = create_db_engine(storage.database_path)
    try:
        options = going_back_options(engine, storage.data_dir)
    finally:
        engine.dispose()
    saved_at = (
        datetime.fromtimestamp(options.backup.stat().st_mtime, UTC).isoformat()
        if options.backup
        else None
    )
    sys.stdout.write(
        json.dumps({"can_undo": options.can_undo, "backup_saved_at": saved_at})
    )
    return 0


def go_back(way: str) -> int:
    """Undo the newer revisions or restore the backup; 1 with the reason on failure."""
    storage = get_storage_settings()
    engine = create_db_engine(storage.database_path)
    try:
        if way == "undo":
            undo_newer_revisions(engine, storage.data_dir)
        else:
            restore_backup(engine, storage.data_dir)
    except Exception as error:
        sys.stderr.write(f"could not go back ({way}): {error}\n")
        return 1
    finally:
        engine.dispose()
    return 0
