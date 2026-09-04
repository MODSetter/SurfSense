import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, func, insert, select

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus, DocumentType

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every document route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def test_a_new_workspace_has_no_documents(
    client: AsyncClient, workspace_id: int
) -> None:
    """The documents view renders its empty state from this."""
    response = await client.get(f"/workspaces/{workspace_id}/documents")

    assert response.status_code == 200
    assert response.json() == []


async def test_an_unknown_workspace_is_not_an_empty_list(client: AsyncClient) -> None:
    """A client polling a deleted workspace has to be told, not shown nothing."""
    response = await client.get("/workspaces/404/documents")

    assert response.status_code == 404


async def test_a_note_starts_pending(client: AsyncClient, workspace_id: int) -> None:
    """A note needs no parsing, but it is not searchable until the worker indexes it."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "# Kickoff\n\nagreed to ship"},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == "NOTE"
    assert response.json()["status"] == "pending"
    assert response.json()["content"] == "# Kickoff\n\nagreed to ship"


async def test_the_list_omits_document_content(
    client: AsyncClient, workspace_id: int
) -> None:
    """The list is polled every couple of seconds; bodies would ride along each time."""
    await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "x" * 5000},
    )

    listed = await client.get(f"/workspaces/{workspace_id}/documents")

    assert "content" not in listed.json()[0]
    assert listed.json()[0]["title"] == "Kickoff"


async def test_a_document_is_read_with_its_content(
    client: AsyncClient, workspace_id: int
) -> None:
    """Opening a document is the one place the extracted text is wanted."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "agreed to ship"},
    )

    response = await client.get(
        f"/workspaces/{workspace_id}/documents/{created.json()['id']}"
    )

    assert response.status_code == 200
    assert response.json()["content"] == "agreed to ship"


async def test_a_document_is_not_readable_through_another_workspace(
    client: AsyncClient, workspace_id: int
) -> None:
    """The workspace in the path is the scope, not decoration on the url."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "secret"},
    )
    other = await client.post("/workspaces", json={"name": "Other"})

    response = await client.get(
        f"/workspaces/{other.json()['id']}/documents/{created.json()['id']}"
    )

    assert response.status_code == 404


async def test_a_document_can_be_retitled(
    client: AsyncClient, workspace_id: int
) -> None:
    """Uploads are titled from a filename, which is rarely what the user would call it."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Untitled", "content": "x"},
    )

    response = await client.patch(
        f"/workspaces/{workspace_id}/documents/{created.json()['id']}",
        json={"title": "Kickoff"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Kickoff"
    assert response.json()["content"] == "x"


async def test_editing_a_note_sends_it_back_for_indexing(
    client: AsyncClient, workspace_id: int
) -> None:
    """Leaving it ready would keep search answering from the text it replaced."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "first draft"},
    )
    document_id = created.json()["id"]

    response = await client.patch(
        f"/workspaces/{workspace_id}/documents/{document_id}",
        json={"content": "second draft"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "second draft"
    assert response.json()["status"] == "pending"


async def test_an_extracted_body_is_not_editable(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """A file's content comes from its bytes; an edit would be lost on re-ingest."""
    with engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                id=1,
                workspace_id=workspace_id,
                title="report.pdf",
                document_type=DocumentType.FILE,
                status=DocumentStatus.READY,
                content="extracted by docling",
            )
        )

    response = await client.patch(
        f"/workspaces/{workspace_id}/documents/1", json={"content": "rewritten"}
    )

    assert response.status_code == 409


async def test_a_deleted_document_takes_its_chunks(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """Chunks left behind would answer searches for a document that is gone."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "x"},
    )
    document_id = created.json()["id"]

    with engine.begin() as connection:
        connection.execute(
            insert(Chunk).values(document_id=document_id, position=0, content="x")
        )

    deleted = await client.delete(f"/workspaces/{workspace_id}/documents/{document_id}")

    assert deleted.status_code == 204
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Chunk)).scalar() == 0


async def test_documents_are_filtered_by_type(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """Studio output shares the table with uploads; the view has to be able to split them."""
    await client.post(
        f"/workspaces/{workspace_id}/documents", json={"title": "note", "content": "x"}
    )
    with engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                id=99,
                workspace_id=workspace_id,
                title="deck",
                document_type=DocumentType.ARTIFACT,
            )
        )

    everything = await client.get(f"/workspaces/{workspace_id}/documents")
    notes_only = await client.get(
        f"/workspaces/{workspace_id}/documents?document_type=NOTE"
    )

    assert len(everything.json()) == 2
    assert [document["title"] for document in notes_only.json()] == ["note"]


async def test_documents_are_filtered_by_status(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """The chat empty state asks whether anything is still being ingested."""
    await client.post(
        f"/workspaces/{workspace_id}/documents", json={"title": "note", "content": "x"}
    )
    with engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                id=99,
                workspace_id=workspace_id,
                title="done",
                document_type=DocumentType.FILE,
                status=DocumentStatus.READY,
            )
        )

    response = await client.get(f"/workspaces/{workspace_id}/documents?status=ready")

    assert [document["title"] for document in response.json()] == ["done"]


async def test_the_list_is_paged(client: AsyncClient, workspace_id: int) -> None:
    """A workspace of a thousand documents must not be re-sent on every poll."""
    for index in range(5):
        await client.post(
            f"/workspaces/{workspace_id}/documents",
            json={"title": f"note {index}", "content": "x"},
        )

    page = await client.get(f"/workspaces/{workspace_id}/documents?limit=2&offset=2")

    assert [document["title"] for document in page.json()] == ["note 2", "note 3"]


async def test_a_failed_document_carries_its_reason(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """The documents view shows this text; without the column it had a badge and no cause."""
    with engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                id=1,
                workspace_id=workspace_id,
                title="broken.pdf",
                document_type=DocumentType.FILE,
                status=DocumentStatus.FAILED,
                error_message="docling could not parse page 3",
            )
        )

    listed = await client.get(f"/workspaces/{workspace_id}/documents")

    assert listed.json()[0]["error_message"] == "docling could not parse page 3"
