"""Integration tests for IndexingPipelineService.migrate_legacy_docs()."""

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


async def test_legacy_composio_gmail_doc_migrated_in_db(
    db_session, db_search_space, db_user, make_connector_document
):
    """A Composio Gmail doc in the DB gets its hash and type updated to native."""
    space_id = db_search_space.id
    user_id = str(db_user.id)
    unique_id = "msg-legacy-123"

    legacy_hash = compute_identifier_hash(
        DocumentType.COMPOSIO_GMAIL_CONNECTOR.value, unique_id, space_id
    )
    native_hash = compute_identifier_hash(
        DocumentType.GOOGLE_GMAIL_CONNECTOR.value, unique_id, space_id
    )

    legacy_doc = Document(
        title="Old Gmail",
        document_type=DocumentType.COMPOSIO_GMAIL_CONNECTOR,
        content="legacy content",
        content_hash=f"ch-{legacy_hash[:12]}",
        unique_identifier_hash=legacy_hash,
        search_space_id=space_id,
        created_by_id=user_id,
        embedding=[0.1] * _EMBEDDING_DIM,
        status={"state": "ready"},
    )
    db_session.add(legacy_doc)
    await db_session.flush()
    doc_id = legacy_doc.id

    connector_doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id=unique_id,
        search_space_id=space_id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])

    result = await db_session.execute(select(Document).filter(Document.id == doc_id))
    reloaded = result.scalars().first()

    assert reloaded.unique_identifier_hash == native_hash
    assert reloaded.document_type == DocumentType.GOOGLE_GMAIL_CONNECTOR


async def test_no_legacy_doc_is_noop(
    db_session, db_search_space, make_connector_document
):
    """When no legacy document exists, migrate_legacy_docs does nothing."""
    connector_doc = make_connector_document(
        document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
        unique_id="evt-no-legacy",
        search_space_id=db_search_space.id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert result.scalars().all() == []


async def test_non_google_type_is_skipped(
    db_session, db_search_space, make_connector_document
):
    """migrate_legacy_docs skips ConnectorDocuments that are not Google types."""
    connector_doc = make_connector_document(
        document_type=DocumentType.CLICKUP_CONNECTOR,
        unique_id="task-1",
        search_space_id=db_search_space.id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])
