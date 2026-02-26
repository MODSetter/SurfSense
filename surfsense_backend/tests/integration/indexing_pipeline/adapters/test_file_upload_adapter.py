import pytest
from sqlalchemy import select

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.adapters.file_upload_adapter import index_uploaded_file

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_sets_status_ready(db_session, db_search_space, db_user, mocker):
    """Document status is READY after successful indexing."""
    await index_uploaded_file(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        session=db_session,
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
    await index_uploaded_file(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        session=db_session,
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
    await index_uploaded_file(
        markdown_content="## Hello\n\nSome content.",
        filename="test.pdf",
        etl_service="UNSTRUCTURED",
        search_space_id=db_search_space.id,
        user_id=str(db_user.id),
        session=db_session,
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
    with pytest.raises(RuntimeError):
        await index_uploaded_file(
            markdown_content="## Hello\n\nSome content.",
            filename="test.pdf",
            etl_service="UNSTRUCTURED",
            search_space_id=db_search_space.id,
            user_id=str(db_user.id),
            session=db_session,
            llm=mocker.Mock(),
        )
