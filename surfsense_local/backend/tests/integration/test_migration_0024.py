"""Revision 0024: a thread keeps the sources the user ticked for it."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def test_an_existing_thread_keeps_its_messages_and_has_no_scope(
    tmp_path: Path,
) -> None:
    """Added in place, so no message cascades away; no scope reads as all sources."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0023")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'w')"))
        connection.execute(
            text("INSERT INTO chat_threads(id, workspace_id, title) VALUES (1, 1, 't')")
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages(chat_thread_id, role, content) "
                "VALUES (1, 'user', '{\"text\": \"hi\"}')"
            )
        )

    command.upgrade(config, "0024")

    with engine.connect() as connection:
        scope = connection.execute(
            text("SELECT source_scope FROM chat_threads")
        ).scalar_one()
        messages = connection.execute(
            text("SELECT count(*) FROM chat_messages")
        ).scalar_one()
    assert scope is None
    assert messages == 1

    command.downgrade(config, "0023")

    columns = {column["name"] for column in inspect(engine).get_columns("chat_threads")}
    assert "source_scope" not in columns
