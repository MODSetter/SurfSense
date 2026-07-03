import pytest
from sqlalchemy import select

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.adapters.file_upload_adapter import UploadDocumentAdapter

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_sets_status_ready(db_session, db_workspace, db_user, mocker):
    """Document status is READY after successful indexing."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    assert DocumentStatus.is_state(document.status, DocumentStatus.READY)


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_content_is_source_markdown(db_session, db_workspace, db_user, mocker):
    """Document content is set to the extracted source markdown."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    assert document.content == "## Hello\n\nSome content."


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_chunks_written_to_db(db_session, db_workspace, db_user, mocker):
    """Chunks derived from the source markdown are persisted in the DB."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    chunks_result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document.id)
    )
    chunks = chunks_result.scalars().all()

    assert len(chunks) == 1
    assert chunks[0].content == "Test chunk content."


@pytest.mark.usefixtures("patched_embed_texts_raises", "patched_chunk_text")
async def test_raises_on_indexing_failure(db_session, db_workspace, db_user, mocker):
    """RuntimeError is raised when the indexing step fails so the caller can fire a failure notification."""
    adapter = UploadDocumentAdapter(db_session)
    with pytest.raises(RuntimeError, match=r"Embedding failed|Indexing failed"):
        await adapter.index(
            markdown_content="## Hello\n\nSome content.",
            filename="test.pdf",
            etl_service="UNSTRUCTURED",
            workspace_id=db_workspace.id,
            user_id=str(db_user.id),
        )


# ---------------------------------------------------------------------------
# reindex() tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_updates_content(db_session, db_workspace, db_user, mocker):
    """Document content is updated to the new source markdown after reindexing."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document)

    await db_session.refresh(document)
    assert document.content == "## Edited\n\nNew content after user edit."


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_updates_content_hash(db_session, db_workspace, db_user, mocker):
    """Content hash is recomputed after reindexing with new source markdown."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()
    original_hash = document.content_hash

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document)

    await db_session.refresh(document)
    assert document.content_hash != original_hash


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_sets_status_ready(db_session, db_workspace, db_user, mocker):
    """Document status is READY after successful reindexing."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document)

    await db_session.refresh(document)
    assert DocumentStatus.is_state(document.status, DocumentStatus.READY)


@pytest.mark.usefixtures("patched_embed_texts")
async def test_reindex_replaces_chunks(db_session, db_workspace, db_user, mocker):
    """Reindexing replaces old chunks with new content rather than appending."""
    mocker.patch(
        "app.indexing_pipeline.cache.cached_indexing.chunk_text_hybrid",
        side_effect=[["Original chunk."], ["Updated chunk."]],
    )

    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()
    document_id = document.id

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document)

    chunks_result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document_id)
    )
    chunks = chunks_result.scalars().all()

    assert len(chunks) == 1
    assert chunks[0].content == "Updated chunk."


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_clears_reindexing_flag(
    db_session, db_workspace, db_user, mocker
):
    """After successful reindex, content_needs_reindexing is False."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    document.content_needs_reindexing = True
    await db_session.flush()

    await adapter.reindex(document=document)

    await db_session.refresh(document)
    assert document.content_needs_reindexing is False


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_raises_on_failure(
    db_session, db_workspace, db_user, patched_embed_texts, mocker
):
    """RuntimeError is raised when reindexing fails so the caller can handle it."""

    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
    )

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == db_workspace.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    patched_embed_texts.side_effect = RuntimeError("Embedding unavailable")

    with pytest.raises(RuntimeError, match=r"Embedding failed|Reindexing failed"):
        await adapter.reindex(document=document)


async def test_reindex_raises_on_empty_source_markdown(
    db_session, db_workspace, db_user, mocker
):
    """Reindexing a document with no source_markdown raises immediately."""
    from app.db import DocumentType

    document = Document(
        title="empty.pdf",
        document_type=DocumentType.FILE,
        content="placeholder",
        content_hash="abc123",
        unique_identifier_hash="def456",
        source_markdown="",
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
    )
    db_session.add(document)
    await db_session.flush()

    adapter = UploadDocumentAdapter(db_session)

    with pytest.raises(RuntimeError, match="no source_markdown"):
        await adapter.reindex(document=document)
