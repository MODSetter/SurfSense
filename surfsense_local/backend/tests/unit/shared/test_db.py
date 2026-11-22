from pathlib import Path

import pytest
from sqlalchemy import text

from shared.db import create_db_engine, serving_request

pytestmark = pytest.mark.unit


async def test_a_request_may_not_open_a_transaction_on_the_event_loop(
    tmp_path: Path,
) -> None:
    """Waiting for SQLite's write lock on the loop would stall every request,
    so a handler that does it fails loudly instead of slowly."""
    engine = create_db_engine(tmp_path / "guard.db")
    token = serving_request.set(True)
    try:
        with pytest.raises(RuntimeError, match="event loop"), engine.begin() as tx:
            tx.execute(text("SELECT 1"))
    finally:
        serving_request.reset(token)

    # Outside a request (startup, tests seeding data) the loop is free to.
    with engine.begin() as tx:
        assert tx.execute(text("SELECT 1")).scalar() == 1


def test_a_connection_can_query_vec0(tmp_path: Path) -> None:
    """Every launch loads sqlite-vec; python.org macOS Python cannot do that."""
    engine = create_db_engine(tmp_path / "vec.db")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT vec_version()").scalar()


def test_a_connection_caps_what_the_write_ahead_log_keeps_on_disk(
    tmp_path: Path,
) -> None:
    """A checkpoint resets the log without shrinking it; past 64 MB a reset truncates it."""
    engine = create_db_engine(tmp_path / "wal.db")
    try:
        with engine.connect() as connection:
            limit = connection.execute(text("PRAGMA journal_size_limit")).scalar()
    finally:
        engine.dispose()

    assert limit == 64 * 1024 * 1024
