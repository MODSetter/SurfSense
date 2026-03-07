from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def patched_summarizer_chain(monkeypatch):
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=MagicMock(content="The summary."))

    template = MagicMock()
    template.__or__ = MagicMock(return_value=chain)

    monkeypatch.setattr(
        "app.indexing_pipeline.document_summarizer.SUMMARY_PROMPT_TEMPLATE",
        template,
    )
    return chain


@pytest.fixture
def patched_chunker_instance(monkeypatch):
    mock = MagicMock()
    mock.chunk.return_value = [MagicMock(text="prose chunk")]
    monkeypatch.setattr(
        "app.indexing_pipeline.document_chunker.config.chunker_instance", mock
    )
    return mock


@pytest.fixture
def patched_code_chunker_instance(monkeypatch):
    mock = MagicMock()
    mock.chunk.return_value = [MagicMock(text="code chunk")]
    monkeypatch.setattr(
        "app.indexing_pipeline.document_chunker.config.code_chunker_instance", mock
    )
    return mock
