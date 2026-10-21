import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import Engine


def load_copy(engine: Engine, copy: Path) -> None:
    """Make the live database hold exactly what `copy` holds.

    Through SQLite's backup API rather than a file swap: it writes the WAL
    correctly, and Windows refuses to replace a file another handle holds.
    """
    raw = engine.raw_connection()
    try:
        uri = f"{copy.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as source:
            source.backup(raw.driver_connection)
    finally:
        raw.close()
    # Pooled connections may hold the replaced schema.
    engine.dispose()
