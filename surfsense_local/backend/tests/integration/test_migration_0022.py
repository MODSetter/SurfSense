"""Revision 0022: the index records which model built it."""

import struct
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command
from modules.embedding.active import active_index
from modules.embedding.bundled import BGE
from shared.db import create_db_engine, create_session_factory
from shared.migrations import upgrade_to_head

pytestmark = pytest.mark.integration


def _at_0021(tmp_path: Path) -> Engine:
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    command.upgrade(config, "0021")
    return engine


def _library(engine: Engine) -> None:
    """One indexed document, and one still waiting for the worker."""
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        for document_id, status in ((1, "ready"), (2, "pending")):
            connection.execute(
                text(
                    "INSERT INTO documents(id, workspace_id, title, document_type, "
                    "status) VALUES (:id, 1, 'note', 'NOTE', :status)"
                ),
                {"id": document_id, "status": status},
            )
        connection.execute(
            text(
                "INSERT INTO chunks(id, document_id, position, content) "
                "VALUES (1, 1, 0, 'the ship sails at dawn')"
            )
        )
        connection.execute(
            text("INSERT INTO chunk_vectors(rowid, embedding) VALUES (1, :vector)"),
            {"vector": struct.pack("384f", *([0.1] * 384))},
        )


def _stamps(engine: Engine) -> dict[int, int | None]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, embedding_index_id FROM documents"))
        return {row.id: row.embedding_index_id for row in rows}


def test_an_existing_library_is_recorded_as_built_by_bge(tmp_path: Path) -> None:
    """Its vectors are bge's, so the row says so; nothing is re-embedded."""
    engine = _at_0021(tmp_path)
    _library(engine)

    upgrade_to_head(engine)

    with create_session_factory(engine)() as session:
        index = active_index(session)
    assert index is not None
    assert index.spec == BGE
    assert index.vector_table == "chunk_vectors"
    assert _stamps(engine) == {1: index.id, 2: None}


def test_a_finished_onboarding_with_no_documents_is_still_bge(
    tmp_path: Path,
) -> None:
    """The choice is offered only before onboarding finishes."""
    engine = _at_0021(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO onboarding_completion(id) VALUES (1)"))

    upgrade_to_head(engine)

    with create_session_factory(engine)() as session:
        index = active_index(session)
    assert index is not None
    assert index.spec == BGE


def test_startup_refuses_an_index_whose_table_is_another_width(
    tmp_path: Path,
) -> None:
    """The row says what wrote the vectors; a table of another width cannot hold them."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    upgrade_to_head(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO embedding_indexes(spec, vector_table, state) "
                "VALUES (:spec, 'chunk_vectors', 'active')"
            ),
            {"spec": BGE.model_copy(update={"dimension": 768}).model_dump_json()},
        )

    with pytest.raises(RuntimeError, match="768"):
        upgrade_to_head(engine)


def test_a_fresh_install_has_not_chosen_yet(tmp_path: Path) -> None:
    """Onboarding offers the choice, so nothing is recorded for it."""
    engine = create_db_engine(tmp_path / "surfsense.db")

    upgrade_to_head(engine)

    with create_session_factory(engine)() as session:
        assert active_index(session) is None
