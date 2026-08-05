"""Query embedding must not be computed on the event loop.

A local embedding model runs a synchronous forward pass that takes tens to
hundreds of milliseconds. Calling it directly from a coroutine stalls every
other request sharing that worker for the duration. The chunk retriever, the
connector service and the chat retrieval path all offload it with
``asyncio.to_thread``; the document retriever was the one place that did not.

The fake model here blocks a real thread, so the assertion is that the loop
kept running while it did -- not that a particular function was called.
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever

pytestmark = pytest.mark.unit


class _BlockingEmbeddingModel:
    """Embeds by blocking a thread until released, like a real forward pass."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def embed(self, _text: str) -> list[float]:
        self.started.set()
        self.release.wait(timeout=5)
        return [0.0, 0.0, 0.0]


class _NoRowsSession:
    """An AsyncSession stand-in that returns an empty result set."""

    async def execute(self, _query):
        return _EmptyResult()


class _EmptyResult:
    def all(self):
        return []

    def scalars(self):
        return self

    def unique(self):
        return self


@pytest.fixture
def blocking_embeddings(monkeypatch):
    from app.config import config

    model = _BlockingEmbeddingModel()
    monkeypatch.setattr(config, "embedding_model_instance", model)
    return model


async def test_vector_search_embeds_without_blocking_the_event_loop(
    blocking_embeddings,
):
    retriever = DocumentHybridSearchRetriever(_NoRowsSession())
    task = asyncio.create_task(
        retriever.vector_search(query_text="anything", top_k=1, workspace_id=1)
    )

    while not blocking_embeddings.started.is_set():
        await asyncio.sleep(0)

    assert not task.done(), "embedding should still be in flight"
    blocking_embeddings.release.set()
    await task


async def test_hybrid_search_embeds_without_blocking_the_event_loop(
    blocking_embeddings,
):
    """Only reached when the caller did not precompute the embedding."""
    retriever = DocumentHybridSearchRetriever(_NoRowsSession())
    task = asyncio.create_task(
        retriever.hybrid_search(query_text="anything", top_k=1, workspace_id=1)
    )

    while not blocking_embeddings.started.is_set():
        await asyncio.sleep(0)

    assert not task.done(), "embedding should still be in flight"
    blocking_embeddings.release.set()
    await task
