"""Every way a source is made files it, so none vanishes from the tree and scopes."""

from pathlib import Path
from zipfile import ZipFile

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, select

from modules.documents.models import Document, DocumentType
from modules.folders.models import Folder
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[5] / "docs/contracts/export-sample"


def _bundle(tmp_path: Path) -> Path:
    path = tmp_path / "export.zip"
    with ZipFile(path, "w") as archive:
        for file in sorted(SAMPLE.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(SAMPLE).as_posix())
    return path


def _sources_without_a_folder(engine: Engine) -> list[str]:
    with create_session_factory(engine)() as session:
        return list(
            session.scalars(
                select(Document.title).where(
                    Document.document_type.in_((DocumentType.FILE, DocumentType.NOTE)),
                    Document.folder_id.is_(None),
                )
            )
        )


async def test_a_note_an_upload_and_an_import_are_all_filed(
    client: AsyncClient, engine: Engine, tmp_path: Path
) -> None:
    """A note an upload and an import are all filed."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    await client.post(
        f"/workspaces/{workspace['id']}/documents",
        json={"title": "Note", "content": "x"},
    )
    await client.post(
        f"/workspaces/{workspace['id']}/documents/upload",
        files={"files": ("a.pdf", b"%PDF-a", "application/pdf")},
    )

    imported = await client.post(
        "/migration/import",
        files={
            "file": ("export.zip", _bundle(tmp_path).read_bytes(), "application/zip")
        },
    )

    assert imported.status_code == 202
    assert _sources_without_a_folder(engine) == []


async def test_an_import_rebuilds_its_folder_paths(
    client: AsyncClient, engine: Engine, tmp_path: Path
) -> None:
    """An import rebuilds its folder paths."""
    imported = await client.post(
        "/migration/import",
        files={
            "file": ("export.zip", _bundle(tmp_path).read_bytes(), "application/zip")
        },
    )
    research = imported.json()["workspaces"][0]["id"]

    with create_session_factory(engine)() as session:
        reading = session.scalar(
            select(Document).where(
                Document.workspace_id == research, Document.title == "Reading list"
            )
        )
        assert reading is not None
        folder = session.get(Folder, reading.folder_id)
        assert folder is not None
        assert folder.name == "Research"


async def test_a_source_left_without_a_folder_still_counts_as_in_the_library(
    client: AsyncClient, engine: Engine
) -> None:
    """The SET NULL backstop must never make a source vanish from every scope."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    note = await client.post(
        f"/workspaces/{workspace['id']}/documents",
        json={"title": "Orphan", "content": "x"},
    )
    with create_session_factory(engine)() as session:
        document = session.get(Document, note.json()["id"])
        assert document is not None
        document.folder_id = None
        session.commit()

    resolved = await client.post(
        f"/workspaces/{workspace['id']}/source-scope/resolve", json={"all": True}
    )
    listed = await client.get(f"/workspaces/{workspace['id']}/documents")

    assert resolved.json()["counts"]["indexing"] == 1
    assert [d["folder_id"] for d in listed.json()] == [None]
