import sqlite3
from contextlib import closing

from huey import SqliteHuey

from shared.config import get_storage_settings
from shared.sqlite import enable_wal

_settings = get_storage_settings()
# SqliteHuey opens the file as it is constructed.
_settings.data_dir.mkdir(parents=True, exist_ok=True)

# Its own file: constant polling must not hold the write lock on the database.
_QUEUE_FILE = str(_settings.queue_path)

# Before huey connects: its own journal_mode switch cannot wait for the lock.
with closing(sqlite3.connect(_QUEUE_FILE, timeout=5)) as _connection:
    enable_wal(_connection)

# One queue per consumer, so an import never queues ahead of a summary.
ingest_queue = SqliteHuey(name="ingest", filename=_QUEUE_FILE)
studio_queue = SqliteHuey(name="studio", filename=_QUEUE_FILE)


def import_tasks() -> None:
    """Import every task; a job carries the name of one, not its code."""
    import modules.artifacts.tasks
    import modules.documents.tasks


def revoke_pending(queue: SqliteHuey, name: str, argument: int) -> None:
    """Skip queued copies of this job; the row is already cancelled."""
    for task in queue.pending():
        if task.name == name and task.args == (argument,):
            queue.revoke(task)
