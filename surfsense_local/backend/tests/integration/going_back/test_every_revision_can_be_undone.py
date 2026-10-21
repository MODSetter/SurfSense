"""Going back to a release runs the undo step of every revision written since it."""

import struct
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command
from shared.db import create_db_engine
from shared.migrations import is_migrated
from tests.integration.going_back.newer_app import ALEMBIC

pytestmark = pytest.mark.integration

# 2.0.0's head. Older revisions belong to releases nobody can go back to.
OLDEST_RELEASED = "0011"

# The tables downgrades rebuild or rewrite, and the rows they must carry through.
TABLES = (
    "workspaces",
    "documents",
    "chunks",
    "chat_threads",
    "chat_messages",
    "artifacts",
    "provider_connections",
    "selected_models",
    "egress_destinations",
)
# Renamed since 0011 rather than added, so a round trip must restore its values.
RENAMED = {"selected_models": {"model_type"}}

ROWS = (
    "INSERT INTO workspaces(id, name) VALUES (1, 'Notes')",
    "INSERT INTO documents(id, workspace_id, title, document_type, status)"
    " VALUES (1, 1, 'note', 'NOTE', 'ready')",
    "INSERT INTO chunks(id, document_id, position, content)"
    " VALUES (1, 1, 0, 'the ship sails at dawn')",
    "INSERT INTO chat_threads(id, workspace_id, title) VALUES (1, 1, 'Plans')",
    "INSERT INTO chat_messages(id, chat_thread_id, role, content)"
    " VALUES (1, 1, 'user', 'when does it sail?')",
    "INSERT INTO artifacts(id, document_id, workspace_id, chat_thread_id, format)"
    " VALUES (1, 1, 1, 1, 'docx')",
    "INSERT INTO provider_connections(id, label, provider, base_url, api_key_ciphertext)"
    " VALUES (1, 'Work', 'openai_compatible', 'https://models.example/v1', x'0102')",
    "INSERT INTO selected_models(model_type, provider, connection_id, name, vendor, line)"
    " VALUES ('text_gen', 'openai_compatible', 1, 'chat-large', 'acme', 'flagship')",
    "INSERT INTO selected_models(model_type, provider, connection_id, name)"
    " VALUES ('image_gen', 'openai_compatible', 1, 'draw-large')",
    "INSERT INTO egress_destinations(destination, enabled) VALUES ('host:huggingface.co', 1)",
)


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    config.attributes["engine"] = engine
    return config


def _columns(engine: Engine) -> dict[str, list[str]]:
    inspector = inspect(engine)
    return {
        table: [column["name"] for column in inspector.get_columns(table)]
        for table in TABLES
    }


def _rows(engine: Engine, columns: dict[str, list[str]]) -> dict[str, list[dict]]:
    with engine.connect() as connection:
        return {
            table: [
                dict(row._mapping)
                for row in connection.execute(
                    text(f"SELECT {', '.join(names)} FROM {table}")
                )
            ]
            for table, names in columns.items()
        }


def _only(
    rows: dict[str, list[dict]], kept: dict[str, list[str]]
) -> dict[str, list[tuple]]:
    return {
        table: sorted(
            tuple(row[column] for column in kept[table]) for row in rows[table]
        )
        for table in kept
    }


def _search_index(engine: Engine) -> tuple[int, int]:
    with engine.connect() as connection:
        return (
            connection.execute(text("SELECT count(*) FROM chunk_vectors")).scalar_one(),
            connection.execute(
                text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'ship'")
            ).scalar_one(),
        )


def _library(path: Path) -> Engine:
    engine = create_db_engine(path)
    command.upgrade(_config(engine), "head")
    with engine.begin() as connection:
        for row in ROWS:
            connection.execute(text(row))
        connection.execute(
            text("INSERT INTO chunk_vectors(rowid, embedding) VALUES (1, :vector)"),
            {"vector": struct.pack("384f", *([0.1] * 384))},
        )
    return engine


def test_every_revision_since_the_first_release_undoes_and_redoes(
    tmp_path: Path,
) -> None:
    """Each undo step since 2.0.0 keeps every row it can hold, and redoes cleanly.

    Columns added after 0011 are left out: undoing drops them by design.
    """
    engine = _library(tmp_path / "surfsense.db")
    at_head = _columns(engine)
    before = _rows(engine, at_head)

    command.downgrade(_config(engine), OLDEST_RELEASED)
    at_oldest = _columns(engine)
    command.upgrade(_config(engine), "head")

    kept = {
        table: [
            column
            for column in at_head[table]
            if column in at_oldest[table] or column in RENAMED.get(table, set())
        ]
        for table in TABLES
    }
    assert _only(_rows(engine, at_head), kept) == _only(before, kept)
    assert _search_index(engine) == (1, 1)
    assert is_migrated(engine)
