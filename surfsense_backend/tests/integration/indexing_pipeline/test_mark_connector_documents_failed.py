"""Integration tests for mark_connector_documents_failed.

Covers the ETL-failure recovery path: a connector placeholder must move out of
``pending``/``processing`` into ``failed`` so it stays deletable, while a
``ready`` document is never clobbered.
"""

import hashlib

import pytest
from sqlalchemy import select

from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.tasks.connector_indexers.base import mark_connector_documents_failed

pytestmark = pytest.mark.integration


async def _make_doc(
    db_session,
    *,
    search_space_id: int,
    connector_id: int,
    user_id: str,
    file_id: str,
    status: dict,
) -> Document:
    uid_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, search_space_id
    )
    doc = Document(
        title=f"{file_id}.pdf",
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        content="Pending...",
        content_hash=hashlib.sha256(f"placeholder:{uid_hash}".encode()).hexdigest(),
        unique_identifier_hash=uid_hash,
        document_metadata={"google_drive_file_id": file_id},
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        status=status,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


async def test_pending_placeholder_marked_failed(
    db_session, db_search_space, db_connector, db_user
):
    doc = await _make_doc(
        db_session,
        search_space_id=db_search_space.id,
        connector_id=db_connector.id,
        user_id=str(db_user.id),
        file_id="file-pending",
        status=DocumentStatus.pending(),
    )

    marked = await mark_connector_documents_failed(
        db_session,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        search_space_id=db_search_space.id,
        failures=[("file-pending", "Download/ETL failed: boom")],
    )

    assert marked == 1
    await db_session.refresh(doc)
    assert DocumentStatus.is_state(doc.status, DocumentStatus.FAILED)
    assert doc.status.get("reason") == "Download/ETL failed: boom"


async def test_ready_document_not_clobbered(
    db_session, db_search_space, db_connector, db_user
):
    doc = await _make_doc(
        db_session,
        search_space_id=db_search_space.id,
        connector_id=db_connector.id,
        user_id=str(db_user.id),
        file_id="file-ready",
        status=DocumentStatus.ready(),
    )

    marked = await mark_connector_documents_failed(
        db_session,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        search_space_id=db_search_space.id,
        failures=[("file-ready", "should be ignored")],
    )

    assert marked == 0
    await db_session.refresh(doc)
    assert DocumentStatus.is_state(doc.status, DocumentStatus.READY)


async def test_missing_document_is_noop(db_session, db_search_space):
    marked = await mark_connector_documents_failed(
        db_session,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        search_space_id=db_search_space.id,
        failures=[("does-not-exist", "reason")],
    )

    assert marked == 0
    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert result.scalars().first() is None
