"""Finding an upload's file in either layout, through the route that serves it."""

from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.fixture
async def uploaded(client: AsyncClient, data_dir: Path) -> tuple[str, Path]:
    """The route serving an upload back, and the one file the upload wrote."""
    workspace = (await client.post("/workspaces", json={"name": "Research"})).json()
    created = await client.post(
        f"/workspaces/{workspace['id']}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7 fake", "application/pdf")},
    )
    document_id = created.json()["created"][0]["id"]
    folder = (
        data_dir
        / "data"
        / "workspaces"
        / str(workspace["id"])
        / "documents"
        / str(document_id)
    )
    url = f"/workspaces/{workspace['id']}/documents/{document_id}/original"
    return url, folder / "report.pdf"


def as_legacy(stored: Path) -> Path:
    """Lay the folder out as uploads were stored before the file kept its name."""
    legacy = stored.with_name("original.pdf")
    stored.rename(legacy)
    (stored.parent / "extracted.md").write_text("# report", encoding="utf-8")
    return legacy


async def test_a_legacy_original_is_found_beside_its_extracted_text(
    client: AsyncClient, uploaded: tuple[str, Path]
) -> None:
    """Folders written before this layout are read as they are, never rewritten."""
    url, stored = uploaded
    as_legacy(stored)

    response = await client.get(url)

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 fake"


async def test_a_deleted_legacy_original_is_missing_not_its_extracted_text(
    client: AsyncClient, uploaded: tuple[str, Path]
) -> None:
    """Serving the markdown would pass Docling's text off as the user's file."""
    url, stored = uploaded
    as_legacy(stored).unlink()

    assert (await client.get(url)).status_code == 404


async def test_files_the_os_leaves_in_the_folder_are_ignored(
    client: AsyncClient, uploaded: tuple[str, Path]
) -> None:
    """Revealing the folder in Finder must not stop the file opening afterwards."""
    url, stored = uploaded
    (stored.parent / ".DS_Store").write_bytes(b"\0")
    (stored.parent / "Thumbs.db").write_bytes(b"\0")

    response = await client.get(url)

    assert response.content == b"%PDF-1.7 fake"


async def test_a_deleted_original_is_missing(
    client: AsyncClient, uploaded: tuple[str, Path]
) -> None:
    """Search and chat keep working from the index; only the file is gone."""
    url, stored = uploaded
    stored.unlink()

    assert (await client.get(url)).status_code == 404
