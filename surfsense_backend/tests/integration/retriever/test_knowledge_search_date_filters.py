"""Integration smoke tests for KB search query/date scoping."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.agents.new_chat.middleware.knowledge_search import search_knowledge_base

from .conftest import DUMMY_EMBEDDING

pytestmark = pytest.mark.integration


async def test_search_knowledge_base_applies_date_filters(
    db_session,
    seed_date_filtered_docs,
    monkeypatch,
):
    """Date filters should remove older matching documents from scoped KB results."""

    @asynccontextmanager
    async def fake_shielded_async_session():
        yield db_session

    monkeypatch.setattr(
        "app.agents.new_chat.middleware.knowledge_search.shielded_async_session",
        fake_shielded_async_session,
    )
    monkeypatch.setattr(
        "app.agents.new_chat.middleware.knowledge_search.embed_texts",
        lambda texts: [np.array(DUMMY_EMBEDDING) for _ in texts],
    )

    space_id = seed_date_filtered_docs["search_space"].id
    recent_cutoff = datetime.now(UTC) - timedelta(days=30)

    unfiltered_results = await search_knowledge_base(
        query="ocv meeting decisions",
        search_space_id=space_id,
        available_document_types=["FILE"],
        top_k=10,
    )
    filtered_results = await search_knowledge_base(
        query="ocv meeting decisions",
        search_space_id=space_id,
        available_document_types=["FILE"],
        top_k=10,
        start_date=recent_cutoff,
        end_date=datetime.now(UTC),
    )

    unfiltered_ids = {result["document"]["id"] for result in unfiltered_results}
    filtered_ids = {result["document"]["id"] for result in filtered_results}

    assert seed_date_filtered_docs["recent_doc"].id in unfiltered_ids
    assert seed_date_filtered_docs["old_doc"].id in unfiltered_ids
    assert seed_date_filtered_docs["recent_doc"].id in filtered_ids
    assert seed_date_filtered_docs["old_doc"].id not in filtered_ids
