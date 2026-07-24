"""Integration tests: Dropbox ConnectorDocuments flow through the pipeline."""

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


def _dropbox_doc(
    *, unique_id: str, workspace_id: int, connector_id: int, user_id: str
) -> ConnectorDocument:
    return ConnectorDocument(
        title=f"File {unique_id}.docx",
        source_markdown=f"## Document\n\nContent from {unique_id}",
        unique_id=unique_id,
        document_type=DocumentType.DROPBOX_FILE,
        workspace_id=workspace_id,
        connector_id=connector_id,
        created_by_id=user_id,
        metadata={
            "dropbox_file_id": unique_id,
            "dropbox_file_name": f"{unique_id}.docx",
            "document_type": "Dropbox File",
        },
    )


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_dropbox_pipeline_creates_ready_document(
    db_session, db_workspace, db_connector, db_user, mocker
):
    """A Dropbox ConnectorDocument flows through prepare + index to a READY document."""
    space_id = db_workspace.id
    doc = _dropbox_doc(
        unique_id="db-file-abc",
        workspace_id=space_id,
        connector_id=db_connector.id,
        user_id=str(db_user.id),
    )

    service = IndexingPipelineService(session=db_session)
    prepared = await service.prepare_for_indexing([doc])
    assert len(prepared) == 1

    await service.index(prepared[0], doc)

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == space_id)
    )
    row = result.scalars().first()

    assert row is not None
    assert row.document_type == DocumentType.DROPBOX_FILE
    assert DocumentStatus.is_state(row.status, DocumentStatus.READY)


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_dropbox_duplicate_content_skipped(
    db_session, db_workspace, db_connector, db_user, mocker
):
    """Re-indexing a Dropbox doc with the same content is skipped (content hash match)."""
    space_id = db_workspace.id
    user_id = str(db_user.id)

    doc = _dropbox_doc(
        unique_id="db-dup-file",
        workspace_id=space_id,
        connector_id=db_connector.id,
        user_id=user_id,
    )

    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([doc])
    assert len(prepared) == 1
    await service.index(prepared[0], doc)

    result = await db_session.execute(
        select(Document).filter(Document.workspace_id == space_id)
    )
    first_doc = result.scalars().first()
    assert first_doc is not None
    doc2 = _dropbox_doc(
        unique_id="db-dup-file",
        workspace_id=space_id,
        connector_id=db_connector.id,
        user_id=user_id,
    )

    prepared2 = await service.prepare_for_indexing([doc2])
    assert len(prepared2) == 0 or (
        len(prepared2) == 1 and prepared2[0].existing_document is not None
    )
