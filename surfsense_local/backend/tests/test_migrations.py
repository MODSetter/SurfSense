"""The upgrade path itself: does it match the models, rerun, and fail cleanly."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from shared.db import Base, create_db_engine
from shared.migrations import upgrade_to_head


def test_migrations_match_the_models(engine: Engine) -> None:
    """Guards the release bug where a model changes and no migration follows."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_migrations_are_idempotent(engine: Engine) -> None:
    """Every launch upgrades to head, so a second pass must be a no-op."""
    upgrade_to_head(engine)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_a_failed_migration_leaves_nothing_behind(tmp_path: Path) -> None:
    """pysqlite autocommits DDL, which would strand a half-upgraded user database."""
    engine = create_db_engine(tmp_path / "surfsense.db")

    with pytest.raises(RuntimeError), engine.begin() as connection:
        connection.execute(text("CREATE TABLE half (id INTEGER)"))
        raise RuntimeError("upgrade died between two create_table calls")

    assert inspect(engine).get_table_names() == []
