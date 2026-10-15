"""Revision 0025: every workspace gets a Library, and every source a folder in it."""

import json
import struct
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine
from shared.migrations import upgrade_to_head

pytestmark = pytest.mark.integration


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _at_0024(tmp_path: Path) -> Engine:
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0024")
    return engine


def _document(
    connection,
    document_id: int,
    workspace_id: int,
    *,
    kind: str = "FILE",
    folder_path: str | None = None,
    dedup_key: str | None = None,
) -> None:
    metadata = {"folder_path": folder_path} if folder_path is not None else None
    connection.execute(
        text(
            "INSERT INTO documents(id, workspace_id, title, document_type, status, "
            "dedup_key, document_metadata) "
            "VALUES (:id, :ws, :title, :kind, 'ready', :dedup, :meta)"
        ),
        {
            "id": document_id,
            "ws": workspace_id,
            "title": f"doc {document_id}",
            "kind": kind,
            "dedup": dedup_key,
            "meta": json.dumps(metadata) if metadata else None,
        },
    )


def _library(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'A')"))
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (2, 'B')"))
        _document(connection, 1, 1, dedup_key="aaa")
        _document(connection, 2, 1, kind="NOTE")
        _document(connection, 3, 1, folder_path="Research/AI", dedup_key="bbb")
        _document(connection, 4, 1, folder_path="research/ai", dedup_key="ccc")
        _document(connection, 5, 1, folder_path="/".join(f"L{n}" for n in range(1, 10)))
        _document(connection, 6, 1, kind="ARTIFACT")
        _document(connection, 7, 2)
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


def _chain(connection, document_id: int) -> list[str]:
    """The folder names from the Library's root folder down to the document."""
    names: list[str] = []
    folder_id = connection.execute(
        text("SELECT folder_id FROM documents WHERE id = :id"), {"id": document_id}
    ).scalar_one()
    while folder_id is not None:
        name, folder_id = connection.execute(
            text("SELECT name, parent_id FROM folders WHERE id = :id"),
            {"id": folder_id},
        ).one()
        names.append(name)
    return list(reversed(names))


def test_each_workspace_gets_one_library_with_its_sources_filed(
    tmp_path: Path,
) -> None:
    """Each workspace gets one library with its sources filed."""
    engine = _at_0024(tmp_path)
    _library(engine)

    upgrade_to_head(engine)

    with engine.connect() as connection:
        roots = connection.execute(
            text("SELECT workspace_id, kind, name FROM source_roots ORDER BY 1")
        ).all()
        assert [tuple(row) for row in roots] == [
            (1, "managed", "Library"),
            (2, "managed", "Library"),
        ]
        assert _chain(connection, 1) == ["Library"]
        assert _chain(connection, 2) == ["Library"]
        assert _chain(connection, 7) == ["Library"]
        # Hosted allowed both spellings; merging them loses no document.
        assert _chain(connection, 3) == ["Library", "Research", "AI"]
        assert _chain(connection, 4) == ["Library", "Research", "AI"]
        # Nine segments: the eighth level holds the rest.
        assert _chain(connection, 5) == [
            "Library",
            *(f"L{n}" for n in range(1, 8)),
            "L8 / L9",
        ]
        # Artifacts start unfiled.
        assert (
            connection.execute(
                text("SELECT folder_id FROM documents WHERE id = 6")
            ).scalar_one()
            is None
        )
        assert connection.execute(text("SELECT count(*) FROM chunks")).scalar_one() == 1
        assert (
            connection.execute(text("SELECT count(*) FROM chunk_vectors")).scalar_one()
            == 1
        )
        hashes = connection.execute(
            text(
                "SELECT id, content_hash FROM documents WHERE id IN (1, 2) ORDER BY id"
            )
        ).all()
        assert [tuple(row) for row in hashes] == [(1, "aaa"), (2, None)]


def test_the_same_bytes_may_sit_in_two_folders_but_not_twice_in_one(
    tmp_path: Path,
) -> None:
    """The same bytes may sit in two folders but not twice in one."""
    engine = _at_0024(tmp_path)
    _library(engine)
    upgrade_to_head(engine)

    with engine.connect() as connection:
        library, research = (
            connection.execute(
                text("SELECT folder_id FROM documents WHERE id IN (1, 3) ORDER BY id")
            )
            .scalars()
            .all()
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO documents(workspace_id, title, document_type, status, "
                "dedup_key, folder_id) "
                "VALUES (1, 'copy', 'FILE', 'ready', 'aaa', :folder)"
            ),
            {"folder": research},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO documents(workspace_id, title, document_type, status, "
                "dedup_key, folder_id) "
                "VALUES (1, 'twin', 'FILE', 'ready', 'aaa', :folder)"
            ),
            {"folder": library},
        )


def test_a_deleted_folder_unfiles_its_documents_rather_than_deleting_them(
    tmp_path: Path,
) -> None:
    """SET NULL is the backstop: a missed purge must never cascade into chunks."""
    engine = _at_0024(tmp_path)
    _library(engine)
    upgrade_to_head(engine)

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM folders WHERE workspace_id = 1"))

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT folder_id FROM documents WHERE workspace_id = 1")
        ).all()
        assert len(rows) == 6
        assert {row.folder_id for row in rows} == {None}
        assert connection.execute(text("SELECT count(*) FROM chunks")).scalar_one() == 1


def test_a_second_run_changes_nothing(tmp_path: Path) -> None:
    """A second run changes nothing."""
    engine = _at_0024(tmp_path)
    _library(engine)
    upgrade_to_head(engine)
    with engine.connect() as connection:
        before = connection.execute(text("SELECT count(*) FROM folders")).scalar_one()

    upgrade_to_head(engine)

    with engine.connect() as connection:
        after = connection.execute(text("SELECT count(*) FROM folders")).scalar_one()
    assert after == before


def test_downgrading_unfiles_everything_and_keeps_every_chunk(tmp_path: Path) -> None:
    """Downgrading unfiles everything and keeps every chunk."""
    engine = _at_0024(tmp_path)
    _library(engine)
    upgrade_to_head(engine)

    command.downgrade(_config(engine), "0024")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM chunks")).scalar_one() == 1
        assert (
            connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 7
        )
