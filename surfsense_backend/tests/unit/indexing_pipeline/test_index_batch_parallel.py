import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.document_hashing import compute_unique_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def pipeline(mock_session):
    return IndexingPipelineService(mock_session)


async def test_index_calls_embed_and_chunk_via_to_thread(
    pipeline, make_connector_document, monkeypatch
):
    """index() runs embed_texts and chunk_text via asyncio.to_thread, not blocking the loop."""
    to_thread_calls = []
    original_to_thread = asyncio.to_thread

    async def tracking_to_thread(func, *args, **kwargs):
        to_thread_calls.append(func.__name__)
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", tracking_to_thread)

    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        AsyncMock(return_value="Summary."),
    )
    mock_chunk = MagicMock(return_value=["chunk1"])
    mock_chunk.__name__ = "chunk_text"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text",
        mock_chunk,
    )
    mock_embed = MagicMock(side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts])
    mock_embed.__name__ = "embed_texts"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.embed_texts",
        mock_embed,
    )

    connector_doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-1",
        search_space_id=1,
    )
    document = MagicMock(spec=Document)
    document.id = 1
    document.status = DocumentStatus.pending()

    await pipeline.index(document, connector_doc, llm=MagicMock())

    assert "chunk_text" in to_thread_calls
    assert "embed_texts" in to_thread_calls
