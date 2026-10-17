from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from shared.going_back.data_folder import set_aside_dir
from shared.going_back.newer_database import database_revision


def set_aside(engine: Engine, data_dir: Path) -> Path:
    """Copy the database before going back changes it. Never pruned: it is the
    only place what the user added in the newer release survives in full."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    target = set_aside_dir(data_dir) / f"{database_revision(engine)}-{stamp}.db"
    partial = target.with_name(target.name + ".partial")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    # Raw, outside any transaction: VACUUM cannot run inside one.
    raw = engine.raw_connection()
    try:
        raw.driver_connection.execute("VACUUM INTO ?", (str(partial),))
    finally:
        raw.close()
    partial.replace(target)
    return target
