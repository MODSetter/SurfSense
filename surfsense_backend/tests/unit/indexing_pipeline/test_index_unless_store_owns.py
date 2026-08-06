from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db import Document
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.unit


@pytest.fixture
def pipeline():
    return IndexingPipelineService(AsyncMock())


def _document(workspace_id: int = 1) -> Document:
    document = MagicMock(spec=Document)
    document.workspace_id = workspace_id
    return document


async def test_a_flipped_workspace_defers_chunking_to_the_store_indexer(pipeline):
    """The store's indexer is the sole chunker for a flipped workspace, so the seam
    must not chunk here; a ``None`` return marks the deferral."""
    pipeline.index = AsyncMock()

    with patch(
        "app.knowledge_store.settings.knowledge_store_enabled_for",
        AsyncMock(return_value=True),
    ):
        result = await pipeline.index_unless_store_owns(_document(), MagicMock())

    assert result is None
    pipeline.index.assert_not_awaited()


async def test_an_unflipped_workspace_still_chunks_here(pipeline):
    """With the store off there is no other chunker, so the seam delegates to
    ``index`` and hands back its document."""
    document = _document()
    pipeline.index = AsyncMock(return_value=document)

    with patch(
        "app.knowledge_store.settings.knowledge_store_enabled_for",
        AsyncMock(return_value=False),
    ):
        result = await pipeline.index_unless_store_owns(document, MagicMock())

    assert result is document
    pipeline.index.assert_awaited_once()
