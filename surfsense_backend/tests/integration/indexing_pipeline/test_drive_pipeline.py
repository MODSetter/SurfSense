"""Integration tests: Drive indexer builds ConnectorDocuments that flow through the pipeline."""

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


def _drive_doc(*, unique_id: str, search_space_id: int, connector_id: int, user_id: str) -> ConnectorDocument:
    return ConnectorDocument(
        title=f"File {unique_id}.pdf",
        source_markdown=f"## Document Content\n\nText from file {unique_id}",
        unique_id=unique_id,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=True,
        fallback_summary=f"File: {unique_id}.pdf",
        metadata={
            "google_drive_file_id": unique_id,
            "google_drive_file_name": f"{unique_id}.pdf",
            "document_type": "Google Drive File",
        },
    )


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_drive_pipeline_creates_ready_document(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A Drive ConnectorDocument flows through prepare + index to a READY document."""
    space_id = db_search_space.id
    doc = _drive_doc(
        unique_id="file-abc",
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
    assert row.document_type == DocumentType.GOOGLE_DRIVE_FILE
    assert DocumentStatus.is_state(row.status, DocumentStatus.READY)


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_drive_legacy_doc_migrated(
    db_session, db_search_space, db_connector, db_user, mocker
):
    """A legacy Composio Drive doc is migrated and reused."""
    space_id = db_search_space.id
    user_id = str(db_user.id)
    file_id = "file-legacy-drive"

    legacy_hash = compute_identifier_hash(
        DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR.value, file_id, space_id
    )
    legacy_doc = Document(
        title="Old Drive File",
        document_type=DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        content="old file summary",
        content_hash=f"ch-{legacy_hash[:12]}",
        unique_identifier_hash=legacy_hash,
        source_markdown="## Old file content",
        search_space_id=space_id,
        created_by_id=user_id,
        embedding=[0.1] * _EMBEDDING_DIM,
        status={"state": "ready"},
    )
    db_session.add(legacy_doc)
    await db_session.flush()
    original_id = legacy_doc.id

    connector_doc = _drive_doc(
        unique_id=file_id,
        search_space_id=space_id,
        connector_id=db_connector.id,
        user_id=user_id,
    )

    service = IndexingPipelineService(session=db_session)
    await service.migrate_legacy_docs([connector_doc])

    result = await db_session.execute(select(Document).filter(Document.id == original_id))
    row = result.scalars().first()

    assert row.document_type == DocumentType.GOOGLE_DRIVE_FILE
    native_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, space_id
    )
    assert row.unique_identifier_hash == native_hash


async def test_should_skip_file_skips_failed_document(
    db_session, db_search_space, db_user,
):
    """A FAILED document with unchanged md5 must be skipped — user can manually retry via Quick Index."""
    import importlib
    import sys
    import types

    pkg = "app.tasks.connector_indexers"
    stub = pkg not in sys.modules
    if stub:
        mod = types.ModuleType(pkg)
        mod.__path__ = ["app/tasks/connector_indexers"]
        mod.__package__ = pkg
        sys.modules[pkg] = mod

    try:
        gdm = importlib.import_module(
            "app.tasks.connector_indexers.google_drive_indexer"
        )
        _should_skip_file = gdm._should_skip_file
    finally:
        if stub:
            sys.modules.pop(pkg, None)

    space_id = db_search_space.id
    file_id = "file-failed-drive"
    md5 = "abc123deadbeef"

    doc_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, space_id
    )
    failed_doc = Document(
        title="Failed File.pdf",
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        content="LLM rate limit exceeded",
        content_hash=f"ch-{doc_hash[:12]}",
        unique_identifier_hash=doc_hash,
        source_markdown="## Real content",
        search_space_id=space_id,
        created_by_id=str(db_user.id),
        embedding=[0.1] * _EMBEDDING_DIM,
        status=DocumentStatus.failed("LLM rate limit exceeded"),
        document_metadata={
            "google_drive_file_id": file_id,
            "google_drive_file_name": "Failed File.pdf",
            "md5_checksum": md5,
        },
    )
    db_session.add(failed_doc)
    await db_session.flush()

    incoming_file = {"id": file_id, "name": "Failed File.pdf", "mimeType": "application/pdf", "md5Checksum": md5}

    should_skip, msg = await _should_skip_file(db_session, incoming_file, space_id)

    assert should_skip, "FAILED documents must be skipped during automatic sync"
    assert "failed" in msg.lower()
