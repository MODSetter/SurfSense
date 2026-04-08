"""Integration tests: Gmail indexer builds ConnectorDocuments that flow through the pipeline."""

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import (
    compute_identifier_hash,
)
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


def _gmail_doc(
    *, unique_id: str, search_space_id: int, connector_id: int, user_id: str
) -> ConnectorDocument:
    """Build a Gmail-style ConnectorDocument like the real indexer does."""
    return ConnectorDocument(
        title=f"Subject for {unique_id}",
        source_markdown=f"## Email\n\nBody of {unique_id}",
        unique_id=unique_id,
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=True,
        fallback_summary=f"Gmail: Subject for {unique_id}",
        metadata={
            "message_id": unique_id,
            "from": "sender@example.com",
            "document_type": "Gmail Message",
        },
    )


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_texts", "patched_chunk_text"
)
async def test_gmail_pipeline_creates_ready_document(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A Gmail ConnectorDocument flows through prepare + index to a READY document."""
    space_id = db_search_space.id
    doc = _gmail_doc(
        unique_id="msg-pipeline-1",
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
    assert row.document_type == DocumentType.GOOGLE_GMAIL_CONNECTOR
    assert DocumentStatus.is_state(row.status, DocumentStatus.READY)
    assert row.source_markdown == doc.source_markdown


@pytest.mark.usefixtures(
    "patched_summarize", "patched_embed_texts", "patched_chunk_text"
)
async def test_gmail_legacy_doc_migrated_then_reused(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A legacy Composio Gmail doc is migrated then reused by the pipeline."""
    space_id = db_search_space.id
    user_id = str(db_user.id)
    msg_id = "msg-legacy-gmail"

    legacy_hash = compute_identifier_hash(
        DocumentType.COMPOSIO_GMAIL_CONNECTOR.value, msg_id, space_id
    )
    legacy_doc = Document(
        title="Old Gmail",
        document_type=DocumentType.COMPOSIO_GMAIL_CONNECTOR,
        content="old summary",
        content_hash=f"ch-{legacy_hash[:12]}",
        unique_identifier_hash=legacy_hash,
        source_markdown="## Old content",
        search_space_id=space_id,
        created_by_id=user_id,
        embedding=[0.1] * _EMBEDDING_DIM,
        status={"state": "ready"},
    )
    db_session.add(legacy_doc)
    await db_session.flush()
    original_id = legacy_doc.id

    connector_doc = _gmail_doc(
        unique_id=msg_id,
        search_space_id=space_id,
        connector_id=db_connector.id,
        user_id=user_id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])

    prepared = await service.prepare_for_indexing([connector_doc])
    assert len(prepared) == 1
    assert prepared[0].id == original_id
    assert prepared[0].document_type == DocumentType.GOOGLE_GMAIL_CONNECTOR

    native_hash = compute_identifier_hash(
        DocumentType.GOOGLE_GMAIL_CONNECTOR.value, msg_id, space_id
    )
    assert prepared[0].unique_identifier_hash == native_hash
