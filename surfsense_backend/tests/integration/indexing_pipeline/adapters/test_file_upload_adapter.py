import pytest
from sqlalchemy import select

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.adapters.file_upload_adapter import UploadDocumentAdapter

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_sets_status_ready(db_session, db_search_space, db_user, mocker):
    """Document status is READY after successful indexing."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    assert DocumentStatus.is_state(document.status, DocumentStatus.READY)


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_content_is_summary(db_session, db_search_space, db_user, mocker):
    """Document content is set to the LLM-generated summary."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    assert document.content == "Mocked summary."


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_chunks_written_to_db(db_session, db_search_space, db_user, mocker):
    """Chunks derived from the source markdown are persisted in the DB."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    chunks_result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document.id)
    )
    chunks = chunks_result.scalars().all()

    assert len(chunks) == 1
    assert chunks[0].content == "Test chunk content."


@pytest.mark.usefixtures(
    "patched_summarize_raises", "patched_embed_text", "patched_chunk_text"
)
async def test_raises_on_indexing_failure(db_session, db_search_space, db_user, mocker):
    """RuntimeError is raised when the indexing step fails so the caller can fire a failure notification."""
    adapter = UploadDocumentAdapter(db_session)
    with pytest.raises(RuntimeError):
        await adapter.index(
            markdown_content="## Hello\n\nSome content.",
            filename="test.pdf",
            etl_service="UNSTRUCTURED",
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            llm=mocker.Mock(),
        )


# ---------------------------------------------------------------------------
# reindex() tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_reindex_sets_status_ready(db_session, db_search_space, db_user, mocker):
    """Document status is READY after successful reindexing."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document, llm=mocker.Mock())

    await db_session.refresh(document)
    assert DocumentStatus.is_state(document.status, DocumentStatus.READY)


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_reindex_replaces_chunks(db_session, db_search_space, db_user, mocker):
    """Reindexing replaces old chunks rather than appending new ones."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()
    document_id = document.id

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    await adapter.reindex(document=document, llm=mocker.Mock())

    chunks_result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document_id)
    )
    chunks = chunks_result.scalars().all()

    assert len(chunks) == 1


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_reindex_clears_reindexing_flag(
    db_session, db_search_space, db_user, mocker
):
    """After successful reindex, content_needs_reindexing is False."""
    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    document.content_needs_reindexing = True
    await db_session.flush()

    await adapter.reindex(document=document, llm=mocker.Mock())

    await db_session.refresh(document)
    assert document.content_needs_reindexing is False


@pytest.mark.usefixtures("patched_embed_text", "patched_chunk_text")
async def test_reindex_raises_on_failure(
    db_session, db_search_space, db_user, mocker
):
    """RuntimeError is raised when reindexing fails so the caller can handle it."""
    mocker.patch(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        return_value="Mocked summary.",
    )

    adapter = UploadDocumentAdapter(db_session)
    await adapter.index(
        markdown_content="## Original\n\nOriginal content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        llm=mocker.Mock(),
    )

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    document = result.scalars().first()

    document.source_markdown = "## Edited\n\nNew content after user edit."
    await db_session.flush()

    mocker.patch(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        side_effect=RuntimeError("LLM unavailable"),
    )

    with pytest.raises(RuntimeError):
        await adapter.reindex(document=document, llm=mocker.Mock())
