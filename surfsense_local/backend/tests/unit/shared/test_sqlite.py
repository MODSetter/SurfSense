import sqlite3
import threading
from pathlib import Path

import pytest

from shared.sqlite import enable_wal

pytestmark = pytest.mark.unit


def test_wal_waits_for_the_process_still_creating_the_file(tmp_path: Path) -> None:
    """A sidecar that opens a fresh file while another is creating its schema
    gets SQLITE_BUSY on the switch, and dies on it without this wait."""
    path = tmp_path / "queue.db"
    creator = sqlite3.connect(path, isolation_level=None)
    creator.execute("CREATE TABLE task (id integer primary key)")
    creator.execute("BEGIN IMMEDIATE")

    latecomer = sqlite3.connect(path, timeout=5, check_same_thread=False)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        latecomer.execute("PRAGMA journal_mode = WAL")

    switch = threading.Thread(target=enable_wal, args=(latecomer,))
    switch.start()
    try:
        assert switch.is_alive()
        creator.execute("COMMIT")
        switch.join(timeout=5)
        assert not switch.is_alive()
        assert latecomer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        switch.join(timeout=5)
        creator.close()
        latecomer.close()


def test_wal_is_a_no_op_once_the_file_is_in_wal(tmp_path: Path) -> None:
    """So a later connection may run the pragma while someone else writes."""
    path = tmp_path / "queue.db"
    first = sqlite3.connect(path)
    enable_wal(first)
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("CREATE TABLE task (id integer primary key)")
    holder.execute("BEGIN IMMEDIATE")

    second = sqlite3.connect(path, timeout=0)
    try:
        enable_wal(second, attempts=1)
    finally:
        holder.close()
        first.close()
        second.close()
