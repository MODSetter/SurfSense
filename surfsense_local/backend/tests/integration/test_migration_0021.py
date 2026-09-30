"""Revision 0021: imported chat threads keep their hosted identity."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

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


def test_chat_threads_gain_a_nullable_unique_cloud_id(tmp_path: Path) -> None:
    """Local threads stay unkeyed; an exported thread id belongs to one row."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0020")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title) "
                "VALUES (1, 1, 'Local')"
            )
        )

    command.upgrade(config, "head")

    cloud_id = next(
        column
        for column in inspect(engine).get_columns("chat_threads")
        if column["name"] == "cloud_id"
    )
    assert cloud_id["nullable"] is True
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT cloud_id FROM chat_threads WHERE id = 1")
            ).scalar_one()
            is None
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO chat_threads(workspace_id, title, cloud_id) "
                "VALUES (1, 'Imported', 501)"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO chat_threads(workspace_id, title, cloud_id) "
                "VALUES (1, 'Duplicate', 501)"
            )
        )


def test_downgrade_keeps_threads_and_removes_the_cloud_id(tmp_path: Path) -> None:
    """Rolling back the identity column does not discard chat history."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title, cloud_id) "
                "VALUES (1, 1, 'Imported', 501)"
            )
        )

    command.downgrade(config, "0020")

    assert "cloud_id" not in {
        column["name"] for column in inspect(engine).get_columns("chat_threads")
    }
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT title FROM chat_threads WHERE id = 1")
            ).scalar_one()
            == "Imported"
        )
