import pytest
from sqlalchemy import select

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_sets_status_ready(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Document status is READY after successful indexing."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.READY)


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_content_is_summary_when_should_summarize_true(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Document content is set to the LLM-generated summary when should_summarize=True."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.content == "Mocked summary."


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_content_is_source_markdown_when_should_summarize_false(
    db_session,
    db_search_space,
    make_connector_document,
):
    """Document content is set to source_markdown verbatim when should_summarize=False."""
    connector_doc = make_connector_document(
        search_space_id=db_search_space.id,
        should_summarize=False,
        source_markdown="## Raw content",
    )
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=None)

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.content == "## Raw content"


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_chunks_written_to_db(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Chunks derived from source_markdown are persisted in the DB."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document_id)
    )
    chunks = result.scalars().all()

    assert len(chunks) == 1
    assert chunks[0].content == "Test chunk content."


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_embedding_written_to_db(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Document embedding vector is persisted in the DB after indexing."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.embedding is not None
    assert len(reloaded.embedding) == 1024


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_updated_at_advances_after_indexing(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """updated_at timestamp is later after indexing than it was at prepare time."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_pending = result.scalars().first().updated_at

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_ready = result.scalars().first().updated_at

    assert updated_at_ready > updated_at_pending


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_no_llm_falls_back_to_source_markdown(
    db_session,
    db_search_space,
    make_connector_document,
):
    """When llm=None and no fallback_summary, content falls back to source_markdown."""
    connector_doc = make_connector_document(
        search_space_id=db_search_space.id,
        should_summarize=True,
        source_markdown="## Fallback content",
    )
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=None)

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.READY)
    assert reloaded.content == "## Fallback content"


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_fallback_summary_used_when_llm_unavailable(
    db_session,
    db_search_space,
    make_connector_document,
):
    """fallback_summary is used as content when llm=None and should_summarize=True."""
    connector_doc = make_connector_document(
        search_space_id=db_search_space.id,
        should_summarize=True,
        source_markdown="## Full raw content",
        fallback_summary="Short pre-built summary.",
    )
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document_id = prepared[0].id

    await service.index(prepared[0], connector_doc, llm=None)

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.READY)
    assert reloaded.content == "Short pre-built summary."


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_reindex_replaces_old_chunks(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Re-indexing a document replaces its old chunks rather than appending."""
    connector_doc = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v1",
    )
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    updated_doc = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v2",
    )
    re_prepared = await service.prepare_for_indexing([updated_doc])
    await service.index(re_prepared[0], updated_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document_id)
    )
    chunks = result.scalars().all()

    assert len(chunks) == 1


@pytest.mark.usefixtures(
    "patched_summarize_raises", "patched_embed_text", "patched_chunk_text"
)
async def test_llm_error_sets_status_failed(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """Document status is FAILED when the LLM raises during indexing."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.FAILED)


@pytest.mark.usefixtures(
    "patched_summarize_raises", "patched_embed_text", "patched_chunk_text"
)
async def test_llm_error_leaves_no_partial_data(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """A failed indexing attempt leaves no partial embedding or chunks in the DB."""
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.embedding is None
    assert reloaded.content == "Pending..."

    chunks_result = await db_session.execute(
        select(Chunk).filter(Chunk.document_id == document_id)
    )
    assert chunks_result.scalars().all() == []
