import pytest
from sqlalchemy import select

from app.db import Document, DocumentStatus
from app.indexing_pipeline.document_hashing import (
    compute_content_hash as real_compute_content_hash,
)
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration


async def test_new_document_is_persisted_with_pending_status(
    db_session, db_search_space, make_connector_document
):
    """A new document is created in the DB with PENDING status and correct markdown."""
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc])

    assert len(results) == 1
    document_id = results[0].id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded is not None
    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.PENDING)
    assert reloaded.source_markdown == doc.source_markdown


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_unchanged_ready_document_is_skipped(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """A READY document with unchanged content is not returned for re-indexing."""
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    # Index fully so the document reaches ready state
    prepared = await service.prepare_for_indexing([doc])
    await service.index(prepared[0], doc, llm=mocker.Mock())

    # Same content on the next run — a ready document must be skipped
    results = await service.prepare_for_indexing([doc])

    assert results == []


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_text", "patched_chunk_text"
)
async def test_title_only_change_updates_title_in_db(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """A title-only change updates the DB title without re-queuing the document."""
    original = make_connector_document(
        search_space_id=db_search_space.id, title="Original Title"
    )
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([original])
    document_id = prepared[0].id
    await service.index(prepared[0], original, llm=mocker.Mock())

    renamed = make_connector_document(
        search_space_id=db_search_space.id, title="Updated Title"
    )
    results = await service.prepare_for_indexing([renamed])

    assert results == []

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.title == "Updated Title"


async def test_changed_content_is_returned_for_reprocessing(
    db_session, db_search_space, make_connector_document
):
    """A document with changed content is returned for re-indexing with updated markdown."""
    original = make_connector_document(
        search_space_id=db_search_space.id, source_markdown="## v1"
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    original_id = first[0].id

    updated = make_connector_document(
        search_space_id=db_search_space.id, source_markdown="## v2"
    )
    results = await service.prepare_for_indexing([updated])

    assert len(results) == 1
    assert results[0].id == original_id

    result = await db_session.execute(
        select(Document).filter(Document.id == original_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.source_markdown == "## v2"
    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.PENDING)


async def test_all_documents_in_batch_are_persisted(
    db_session, db_search_space, make_connector_document
):
    """All documents in a batch are persisted and returned."""
    docs = [
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="id-1",
            title="Doc 1",
            source_markdown="## Content 1",
        ),
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="id-2",
            title="Doc 2",
            source_markdown="## Content 2",
        ),
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="id-3",
            title="Doc 3",
            source_markdown="## Content 3",
        ),
    ]
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing(docs)

    assert len(results) == 3

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    rows = result.scalars().all()

    assert len(rows) == 3


async def test_duplicate_in_batch_is_persisted_once(
    db_session, db_search_space, make_connector_document
):
    """The same document passed twice in a batch is only persisted once."""
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc, doc])

    assert len(results) == 1

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    rows = result.scalars().all()

    assert len(rows) == 1


async def test_created_by_id_is_persisted(
    db_session, db_user, db_search_space, make_connector_document
):
    """created_by_id from the connector document is persisted on the DB row."""
    doc = make_connector_document(
        search_space_id=db_search_space.id,
        created_by_id=str(db_user.id),
    )
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc])
    document_id = results[0].id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert str(reloaded.created_by_id) == str(db_user.id)


async def test_metadata_is_updated_when_content_changes(
    db_session, db_search_space, make_connector_document
):
    """document_metadata is overwritten with the latest metadata when content changes."""
    original = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v1",
        metadata={"status": "in_progress"},
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    updated = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v2",
        metadata={"status": "done"},
    )
    await service.prepare_for_indexing([updated])

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.document_metadata == {"status": "done"}


async def test_updated_at_advances_when_title_only_changes(
    db_session, db_search_space, make_connector_document
):
    """updated_at advances even when only the title changes."""
    original = make_connector_document(
        search_space_id=db_search_space.id, title="Old Title"
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_v1 = result.scalars().first().updated_at

    renamed = make_connector_document(
        search_space_id=db_search_space.id, title="New Title"
    )
    await service.prepare_for_indexing([renamed])

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_v2 = result.scalars().first().updated_at

    assert updated_at_v2 > updated_at_v1


async def test_updated_at_advances_when_content_changes(
    db_session, db_search_space, make_connector_document
):
    """updated_at advances when document content changes."""
    original = make_connector_document(
        search_space_id=db_search_space.id, source_markdown="## v1"
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_v1 = result.scalars().first().updated_at

    updated = make_connector_document(
        search_space_id=db_search_space.id, source_markdown="## v2"
    )
    await service.prepare_for_indexing([updated])

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    updated_at_v2 = result.scalars().first().updated_at

    assert updated_at_v2 > updated_at_v1


async def test_same_content_from_different_source_skipped_in_single_batch(
    db_session, db_search_space, make_connector_document
):
    """Two documents with identical content in the same batch result in only one being persisted."""
    first = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-a",
        source_markdown="## Shared content",
    )
    second = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-b",
        source_markdown="## Shared content",
    )
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([first, second])

    assert len(results) == 1

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert len(result.scalars().all()) == 1


async def test_same_content_from_different_source_is_skipped(
    db_session, db_search_space, make_connector_document
):
    """A document with content identical to an already-indexed document is skipped."""
    first = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-a",
        source_markdown="## Shared content",
    )
    second = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-b",
        source_markdown="## Shared content",
    )
    service = IndexingPipelineService(session=db_session)

    await service.prepare_for_indexing([first])
    results = await service.prepare_for_indexing([second])

    assert results == []

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.usefixtures(
    "patched_summarize_raises", "patched_embed_text", "patched_chunk_text"
)
async def test_failed_document_with_unchanged_content_is_requeued(
    db_session,
    db_search_space,
    make_connector_document,
    mocker,
):
    """A FAILED document with unchanged content is re-queued as PENDING on the next run."""
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    # First run: document is created and indexing crashes → status = failed
    prepared = await service.prepare_for_indexing([doc])
    document_id = prepared[0].id
    await service.index(prepared[0], doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    assert DocumentStatus.is_state(
        result.scalars().first().status, DocumentStatus.FAILED
    )

    # Next run: same content, pipeline must re-queue the failed document
    results = await service.prepare_for_indexing([doc])

    assert len(results) == 1
    assert results[0].id == document_id

    result = await db_session.execute(
        select(Document).filter(Document.id == document_id)
    )
    assert DocumentStatus.is_state(
        result.scalars().first().status, DocumentStatus.PENDING
    )


async def test_title_and_content_change_updates_both_and_returns_document(
    db_session, db_search_space, make_connector_document
):
    """When both title and content change, both are updated and the document is returned for re-indexing."""
    original = make_connector_document(
        search_space_id=db_search_space.id,
        title="Original Title",
        source_markdown="## v1",
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    original_id = first[0].id

    updated = make_connector_document(
        search_space_id=db_search_space.id,
        title="Updated Title",
        source_markdown="## v2",
    )
    results = await service.prepare_for_indexing([updated])

    assert len(results) == 1
    assert results[0].id == original_id

    result = await db_session.execute(
        select(Document).filter(Document.id == original_id)
    )
    reloaded = result.scalars().first()

    assert reloaded.title == "Updated Title"
    assert reloaded.source_markdown == "## v2"


async def test_one_bad_document_in_batch_does_not_prevent_others_from_being_persisted(
    db_session,
    db_search_space,
    make_connector_document,
    monkeypatch,
):
    """
    A per-document error during prepare_for_indexing must be isolated.
    The two valid documents around the failing one must still be persisted.
    """
    docs = [
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="good-1",
            source_markdown="## Good doc 1",
        ),
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="will-fail",
            source_markdown="## Bad doc",
        ),
        make_connector_document(
            search_space_id=db_search_space.id,
            unique_id="good-2",
            source_markdown="## Good doc 2",
        ),
    ]

    def compute_content_hash_with_error(doc):
        if doc.unique_id == "will-fail":
            raise RuntimeError("Simulated per-document failure")
        return real_compute_content_hash(doc)

    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.compute_content_hash",
        compute_content_hash_with_error,
    )

    service = IndexingPipelineService(session=db_session)
    results = await service.prepare_for_indexing(docs)

    assert len(results) == 2

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert len(result.scalars().all()) == 2
