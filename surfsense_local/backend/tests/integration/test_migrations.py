"""The upgrade path itself: does it match the models, rerun, and fail cleanly."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from alembic import command
from shared.db import Base, create_db_engine
from shared.migrations import upgrade_to_head

pytestmark = pytest.mark.integration

# fts5 and vec0 each spread over half a dozen shadow tables that no model
# declares and nothing should query directly.
SEARCH_INDEX = ("chunks_fts", "chunk_vectors")


def _drift_from_models(engine: Engine) -> list:
    def is_mapped(name: str | None, type_: str, _parents: dict) -> bool:
        return not (
            type_ == "table" and name is not None and name.startswith(SEARCH_INDEX)
        )

    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"include_name": is_mapped}
        )
        return compare_metadata(context, Base.metadata)


def test_migrations_match_the_models(engine: Engine) -> None:
    """Guards the release bug where a model changes and no migration follows."""
    assert _drift_from_models(engine) == []


def test_migrations_are_idempotent(engine: Engine) -> None:
    """Every launch upgrades to head, so a second pass must be a no-op."""
    upgrade_to_head(engine)

    assert _drift_from_models(engine) == []


def test_a_failed_migration_leaves_nothing_behind(tmp_path: Path) -> None:
    """pysqlite autocommits DDL, which would strand a half-upgraded user database."""
    engine = create_db_engine(tmp_path / "surfsense.db")

    with pytest.raises(RuntimeError), engine.begin() as connection:
        connection.execute(text("CREATE TABLE half (id INTEGER)"))
        raise RuntimeError("upgrade died between two create_table calls")

    assert inspect(engine).get_table_names() == []


def test_connection_migration_preserves_only_ollama_selection(
    tmp_path: Path,
) -> None:
    """The breaking migration drops old remote secrets without harming local setup."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    command.upgrade(config, "0003")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(role, provider, name) "
                "VALUES ('generation', 'ollama', 'qwen3:4b')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO provider_credentials(provider, api_key) "
                "VALUES ('openrouter', 'secret')"
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        selected = connection.execute(
            text(
                "SELECT role, provider, connection_id, name FROM selected_models"
            )
        ).one()
        tables = inspect(connection).get_table_names()
    assert tuple(selected) == ("generation", "ollama", None, "qwen3:4b")
    assert "provider_credentials" not in tables
    assert "provider_connections" in tables
