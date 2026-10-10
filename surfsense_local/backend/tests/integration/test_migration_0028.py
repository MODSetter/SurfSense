"""Revision 0028: imported chat threads keep their hosted identity."""

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


def test_chat_threads_gain_identity_without_reimporting_legacy_history(
    tmp_path: Path,
) -> None:
    """The old importer's message signature marks user and assistant-only history."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0027")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspaces(id, name, cloud_id) "
                "VALUES (1, 'Imported', 12), (2, 'Interrupted', 13), "
                "(3, 'Local', NULL), (4, 'Assistant only', 14)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title) "
                "VALUES (1, 1, 'Imported thread'), (2, 3, 'Local thread'), "
                "(3, 2, 'Local turn after interrupted import'), "
                "(4, 4, 'Imported assistant only')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages("
                "id, chat_thread_id, role, content, created_at, completed_at"
                ") VALUES "
                """(1, 1, 'user', '{"text": "kept", "citations": []}', """
                "'2026-06-01 10:00:00', '2026-06-01 10:00:00'), "
                """(2, 3, 'user', '{"text": "local"}', """
                "'2026-06-02 10:00:00', NULL), "
                """(3, 3, 'assistant', '{"text": "answer", "citations": []}', """
                "'2026-06-02 10:00:01', '2026-06-02 10:00:02'), "
                """(4, 4, 'assistant', '{"text": "imported", "citations": []}', """
                "'2026-06-03 10:00:00', '2026-06-03 10:00:00')"
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
        assert connection.execute(
            text("SELECT id, has_unkeyed_imported_threads FROM workspaces ORDER BY id")
        ).all() == [(1, 1), (2, 0), (3, 0), (4, 1)]
        assert (
            connection.execute(
                text("SELECT content FROM chat_messages WHERE id = 1")
            ).scalar_one()
            == '{"text": "kept", "citations": []}'
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
        connection.execute(
            text(
                "INSERT INTO chat_messages(id, chat_thread_id, role, content) "
                """VALUES (1, 1, 'user', '{"text": "kept"}')"""
            )
        )

    command.downgrade(config, "0027")

    assert "cloud_id" not in {
        column["name"] for column in inspect(engine).get_columns("chat_threads")
    }
    assert "has_unkeyed_imported_threads" not in {
        column["name"] for column in inspect(engine).get_columns("workspaces")
    }
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT title FROM chat_threads WHERE id = 1")
            ).scalar_one()
            == "Imported"
        )
        assert (
            connection.execute(
                text("SELECT content FROM chat_messages WHERE id = 1")
            ).scalar_one()
            == '{"text": "kept"}'
        )
