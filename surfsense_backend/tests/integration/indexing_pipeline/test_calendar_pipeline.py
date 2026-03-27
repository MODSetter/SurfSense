"""Integration tests: Calendar indexer builds ConnectorDocuments that flow through the pipeline."""

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


def _cal_doc(*, unique_id: str, search_space_id: int, connector_id: int, user_id: str) -> ConnectorDocument:
    return ConnectorDocument(
        title=f"Event {unique_id}",
        source_markdown=f"## Calendar Event\n\nDetails for {unique_id}",
        unique_id=unique_id,
        document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=True,
        fallback_summary=f"Calendar: Event {unique_id}",
        metadata={
            "event_id": unique_id,
            "start_time": "2025-01-15T10:00:00",
            "end_time": "2025-01-15T11:00:00",
            "document_type": "Google Calendar Event",
        },
    )


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_calendar_pipeline_creates_ready_document(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A Calendar ConnectorDocument flows through prepare + index to a READY document."""
    space_id = db_search_space.id
    doc = _cal_doc(
        unique_id="evt-1",
        search_space_id=space_id,
        connector_id=db_connector.id,
        user_id=str(db_user.id),
    )

    service = IndexingPipelineService(session=db_session)
    prepared = await service.prepare_for_indexing([doc])
    assert len(prepared) == 1

    await service.index(prepared[0], doc, llm=mocker.Mock())

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == space_id)
    )
    row = result.scalars().first()

    assert row is not None
    assert row.document_type == DocumentType.GOOGLE_CALENDAR_CONNECTOR
    assert DocumentStatus.is_state(row.status, DocumentStatus.READY)


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_calendar_legacy_doc_migrated(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A legacy Composio Calendar doc is migrated and reused."""
    space_id = db_search_space.id
    user_id = str(db_user.id)
    evt_id = "evt-legacy-cal"

    legacy_hash = compute_identifier_hash(
        DocumentType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR.value, evt_id, space_id
    )
    legacy_doc = Document(
        title="Old Calendar Event",
        document_type=DocumentType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        content="old summary",
        content_hash=f"ch-{legacy_hash[:12]}",
        unique_identifier_hash=legacy_hash,
        source_markdown="## Old event",
        search_space_id=space_id,
        created_by_id=user_id,
        embedding=[0.1] * _EMBEDDING_DIM,
        status={"state": "ready"},
    )
    db_session.add(legacy_doc)
    await db_session.flush()
    original_id = legacy_doc.id

    connector_doc = _cal_doc(
        unique_id=evt_id,
        search_space_id=space_id,
        connector_id=db_connector.id,
        user_id=user_id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])

    result = await db_session.execute(select(Document).filter(Document.id == original_id))
    row = result.scalars().first()

    assert row.document_type == DocumentType.GOOGLE_CALENDAR_CONNECTOR
    native_hash = compute_identifier_hash(
        DocumentType.GOOGLE_CALENDAR_CONNECTOR.value, evt_id, space_id
    )
    assert row.unique_identifier_hash == native_hash
