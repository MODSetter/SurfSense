import asyncio
from unittest.mock import AsyncMock, MagicMock

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


def _make_orm_doc(connector_doc, doc_id):
    """Create a MagicMock Document bound to a ConnectorDocument's hash."""
    doc = MagicMock(spec=Document)
    doc.id = doc_id
    doc.unique_identifier_hash = compute_unique_identifier_hash(connector_doc)
    doc.status = DocumentStatus.pending()
    return doc


async def test_index_calls_embed_and_chunk_via_to_thread(
    pipeline, make_connector_document, monkeypatch
):
    """index() runs the chunker and embed_texts via asyncio.to_thread, not blocking the loop.

    Routing between ``chunk_text`` (code path) and ``chunk_text_hybrid`` (default
    path, see issue #1334) is verified separately in
    ``test_non_code_documents_use_hybrid_chunker``.
    """
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
    mock_chunk_hybrid = MagicMock(return_value=["chunk1"])
    mock_chunk_hybrid.__name__ = "chunk_text_hybrid"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text_hybrid",
        mock_chunk_hybrid,
    )
    mock_embed = MagicMock(
        side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts]
    )
    mock_embed.__name__ = "embed_texts"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.embed_texts",
        mock_embed,
    )
    # Bypass set_committed_value, which requires a real ORM instance (not MagicMock).
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.attach_chunks_to_document",
        MagicMock(),
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

    # Either chunker entry point satisfies the "chunking runs off the event
    # loop" contract this test guards. Routing between the two is verified
    # in test_non_code_documents_use_hybrid_chunker.
    assert {"chunk_text", "chunk_text_hybrid"} & set(to_thread_calls)
    assert "embed_texts" in to_thread_calls
    assert document.status == DocumentStatus.ready()


async def test_non_code_documents_use_hybrid_chunker(
    pipeline, make_connector_document, monkeypatch
):
    """Non-code documents route through ``chunk_text_hybrid`` (issue #1334).

    The hybrid chunker preserves Markdown table integrity by avoiding splits
    mid-row. Only documents flagged with ``should_use_code_chunker=True``
    should take the ``chunk_text`` path.
    """
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        AsyncMock(return_value="Summary."),
    )
    mock_chunk_hybrid = MagicMock(return_value=["chunk1"])
    mock_chunk_hybrid.__name__ = "chunk_text_hybrid"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text_hybrid",
        mock_chunk_hybrid,
    )
    mock_chunk_code = MagicMock(return_value=["chunk1"])
    mock_chunk_code.__name__ = "chunk_text"
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text",
        mock_chunk_code,
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.embed_texts",
        MagicMock(side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts]),
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.attach_chunks_to_document",
        MagicMock(),
    )

    connector_doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-1",
        search_space_id=1,
        should_use_code_chunker=False,
    )
    document = MagicMock(spec=Document)
    document.id = 1
    document.status = DocumentStatus.pending()

    await pipeline.index(document, connector_doc, llm=MagicMock())

    mock_chunk_hybrid.assert_called_once()
    mock_chunk_code.assert_not_called()


def _mock_session_factory(orm_docs_by_id):
    """Replace get_celery_session_maker with a two-level callable.

    get_celery_session_maker() -> session_maker
    session_maker()            -> async context manager yielding a mock session
    """

    def _get_maker():
        def _make_session():
            session = MagicMock()
            session.get = AsyncMock(
                side_effect=lambda model, doc_id: orm_docs_by_id.get(doc_id)
            )
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=session)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        return _make_session

    return _get_maker


async def test_batch_parallel_indexes_all_documents(
    pipeline, make_connector_document, monkeypatch
):
    """index_batch_parallel indexes all documents and returns correct counts."""
    docs = [
        make_connector_document(
            document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
            unique_id=f"msg-{i}",
            search_space_id=1,
        )
        for i in range(3)
    ]

    orm_docs = [_make_orm_doc(cd, doc_id=i + 1) for i, cd in enumerate(docs)]
    pipeline.prepare_for_indexing = AsyncMock(return_value=orm_docs)

    orm_by_id = {d.id: d for d in orm_docs}
    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker",
        _mock_session_factory(orm_by_id),
    )

    index_calls = []

    async def fake_index(self, document, connector_doc, llm):
        index_calls.append(document.id)
        document.status = DocumentStatus.ready()
        return document

    monkeypatch.setattr(IndexingPipelineService, "index", fake_index)

    async def mock_get_llm(session):
        return MagicMock()

    _, indexed, failed = await pipeline.index_batch_parallel(
        docs, mock_get_llm, max_concurrency=2
    )

    assert indexed == 3
    assert failed == 0
    assert sorted(index_calls) == [1, 2, 3]


async def test_batch_parallel_one_failure_does_not_affect_others(
    pipeline, make_connector_document, monkeypatch
):
    """One document failure doesn't prevent other documents from being indexed."""
    docs = [
        make_connector_document(
            document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
            unique_id=f"msg-{i}",
            search_space_id=1,
        )
        for i in range(3)
    ]

    orm_docs = [_make_orm_doc(cd, doc_id=i + 1) for i, cd in enumerate(docs)]
    pipeline.prepare_for_indexing = AsyncMock(return_value=orm_docs)

    orm_by_id = {d.id: d for d in orm_docs}
    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker",
        _mock_session_factory(orm_by_id),
    )

    async def failing_index(self, document, connector_doc, llm):
        if document.id == 2:
            raise RuntimeError("LLM exploded")
        document.status = DocumentStatus.ready()
        return document

    monkeypatch.setattr(IndexingPipelineService, "index", failing_index)

    async def mock_get_llm(session):
        return MagicMock()

    _, indexed, failed = await pipeline.index_batch_parallel(
        docs, mock_get_llm, max_concurrency=4
    )

    assert indexed == 2
    assert failed == 1
