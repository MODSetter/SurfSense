"""Locking: the moment the library's embedder is chosen for good."""

import struct
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from modules.embedding.active import active_index
from modules.embedding.bundled import BGE
from modules.embedding.lock import IndexAlreadyBuiltError, lock_index
from shared.db import create_db_engine, create_session_factory
from shared.migrations import upgrade_to_head

pytestmark = pytest.mark.integration

NARROW = BGE.model_copy(update={"id": "narrow", "dimension": 8})


@pytest.fixture
def fresh(tmp_path: Path) -> Engine:
    """An install whose onboarding has not chosen an embedder."""
    engine = create_db_engine(tmp_path / "fresh.db")
    upgrade_to_head(engine)
    return engine


def _store(engine: Engine, table: str, width: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO {table}(rowid, embedding) VALUES (1, :vector)"),
            {"vector": struct.pack(f"{width}f", *([0.1] * width))},
        )


def test_the_chosen_model_becomes_the_active_index(fresh: Engine) -> None:
    """Search reads it and ingest writes it from here on."""
    with create_session_factory(fresh)() as session:
        lock_index(session, NARROW)
        session.commit()
        index = active_index(session)

    assert index is not None
    assert index.spec == NARROW


def test_its_table_holds_vectors_of_the_models_width(fresh: Engine) -> None:
    """Built at the chosen width, not the width the first migration guessed."""
    with create_session_factory(fresh)() as session:
        lock_index(session, NARROW)
        session.commit()
        table = active_index(session).vector_table

    _store(fresh, table, 8)
    with pytest.raises(OperationalError):
        _store(fresh, table, 384)


def test_a_library_with_chunks_cannot_be_locked_again(fresh: Engine) -> None:
    """Its vectors were made by some model already; a new one would not match."""
    with fresh.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'w')"))
        connection.execute(
            text(
                "INSERT INTO documents(id, workspace_id, title, document_type, "
                "status) VALUES (1, 1, 'n', 'NOTE', 'ready')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chunks(document_id, position, content) "
                "VALUES (1, 0, 'text')"
            )
        )

    with (
        create_session_factory(fresh)() as session,
        pytest.raises(IndexAlreadyBuiltError),
    ):
        lock_index(session, NARROW)


def test_a_locked_library_cannot_be_locked_again(fresh: Engine) -> None:
    """The choice is made once; changing it is a re-embed, not a second lock."""
    with create_session_factory(fresh)() as session:
        lock_index(session, BGE)
        session.commit()

        with pytest.raises(IndexAlreadyBuiltError):
            lock_index(session, NARROW)
