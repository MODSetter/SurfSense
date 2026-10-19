"""Revision 0032: each agent thread records the engine that runs it."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
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


def _upgraded_with_two_threads(tmp_path: Path) -> Engine:
    """An agent thread and a chat thread, made before the revision."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0031")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'W')"))
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title, opencode_session_id) "
                "VALUES (1, 1, 'Agent', 'ses_1'), (2, 1, 'Chat', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages(id, chat_thread_id, role, content) "
                """VALUES (1, 2, 'user', '{"text": "kept"}')"""
            )
        )
    command.upgrade(config, "head")
    return engine


def test_agent_threads_are_opencodes_and_chat_threads_have_no_engine(
    tmp_path: Path,
) -> None:
    """Every agent thread so far ran on opencode; a chat thread keeps its messages."""
    engine = _upgraded_with_two_threads(tmp_path)

    with engine.connect() as connection:
        engines = dict(
            connection.execute(text("SELECT id, agent_engine FROM chat_threads")).all()
        )
        messages = connection.execute(
            text("SELECT count(*) FROM chat_messages WHERE chat_thread_id = 2")
        ).scalar_one()
    assert engines == {1: "opencode", 2: None}
    assert messages == 1


def test_an_engine_outside_the_two_is_refused(tmp_path: Path) -> None:
    """A typo in code would otherwise route a thread to no engine at all."""
    engine = _upgraded_with_two_threads(tmp_path)

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE chat_threads SET agent_engine = 'codex' WHERE id = 1")
        )


def test_a_threads_claude_transcript_and_endings_go_with_it(tmp_path: Path) -> None:
    """Deleting the thread deletes SurfSense's copy of its Claude Code session."""
    engine = _upgraded_with_two_threads(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE chat_threads SET agent_engine = 'claude_code', "
                "claude_session_id = 's-1' WHERE id = 1"
            )
        )
        connection.execute(
            text(
                "INSERT INTO claude_session_entries(thread_id, session_id, uuid, entry) "
                """VALUES (1, 's-1', 'e-1', '{"type": "user"}')"""
            )
        )
        connection.execute(
            text(
                "INSERT INTO claude_reply_endings(thread_id, reply_id, ending) "
                """VALUES (1, 'e-1:reply', '{"type": "stopped"}')"""
            )
        )

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM chat_threads WHERE id = 1"))

    with engine.connect() as connection:
        left = [
            connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in ("claude_session_entries", "claude_reply_endings")
        ]
    assert left == [0, 0]


def test_an_entry_is_kept_once_per_session(tmp_path: Path) -> None:
    """The SDK retries a batch that may have landed; its uuid makes the retry a no-op."""
    engine = _upgraded_with_two_threads(tmp_path)
    insert = text(
        "INSERT INTO claude_session_entries(thread_id, session_id, uuid, entry) "
        """VALUES (1, 's-1', 'e-1', '{"type": "user"}')"""
    )
    with engine.begin() as connection:
        connection.execute(insert)

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert)
