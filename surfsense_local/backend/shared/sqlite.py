import sqlite3
import time
from typing import Any

# Switching a fresh file to WAL wants an exclusive lock, and SQLite answers
# SQLITE_BUSY without running the busy handler, so busy_timeout does not cover
# it. ponytail: fixed 5s poll, matching busy_timeout; it only ever waits on
# another process creating a schema.
_ATTEMPTS = 50
_DELAY = 0.1

_LOAD_EXTENSION_HINT = (
    "SQLite was built without loadable extensions, so vec0 cannot load. "
    "On macOS freeze with uv's Python (python-build-standalone), not "
    "python.org or Apple's: UV_PYTHON_PREFERENCE=only-managed"
)


def require_load_extension(connection: Any) -> None:
    """Fail before sqlite-vec if this Python omitted enable_load_extension.

    python.org macOS builds skip --enable-loadable-sqlite-extensions; Apple's
    Python does too. The method is then missing, and the first connection
    (migrations on launch) dies with AttributeError.
    """
    if not hasattr(connection, "enable_load_extension"):
        raise RuntimeError(_LOAD_EXTENSION_HINT)


def enable_wal(connection: Any, attempts: int = _ATTEMPTS) -> None:
    """Put a SQLite file in WAL mode, waiting out a concurrent first opener."""
    for remaining in reversed(range(attempts)):
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError:
            if not remaining:
                raise
            time.sleep(_DELAY)
