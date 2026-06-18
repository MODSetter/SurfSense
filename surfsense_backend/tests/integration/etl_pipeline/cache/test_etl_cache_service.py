"""EtlCacheService end-to-end against real Postgres + real local storage.

Exercises the public cache surface -- ``recall`` / ``remember`` -- with no mocks:
a miss returns nothing, and a remembered parse comes back as an equivalent
``EtlResult`` rebuilt from the row and the blob.
"""

from __future__ import annotations

import pytest

from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.service import EtlCacheService
from app.etl_pipeline.etl_document import EtlResult

pytestmark = pytest.mark.integration


def _key(sha: str = "c" * 64) -> ParseKey:
    return ParseKey.for_document(sha, etl_service="LLAMACLOUD", mode="basic", version=1)


async def test_recall_is_a_miss_for_an_unknown_key(db_session, cache_local_storage):
    service = EtlCacheService(db_session)
    assert await service.recall(_key()) is None


async def test_remembered_parse_recalls_as_equivalent_result(
    db_session, cache_local_storage
):
    service = EtlCacheService(db_session)
    stored = EtlResult(
        markdown_content="# Cached doc\n\nBody paragraph.\n",
        etl_service="LLAMACLOUD",
        actual_pages=7,
        content_type="application/pdf",
    )

    await service.remember(_key(), stored)
    recalled = await service.recall(_key())

    assert recalled is not None
    assert recalled.markdown_content == stored.markdown_content
    assert recalled.etl_service == "LLAMACLOUD"
    assert recalled.actual_pages == 7
    assert recalled.content_type == "application/pdf"


async def test_repeated_recall_keeps_serving_the_same_content(
    db_session, cache_local_storage
):
    service = EtlCacheService(db_session)
    stored = EtlResult(
        markdown_content="# Stable\n",
        etl_service="LLAMACLOUD",
        actual_pages=1,
        content_type="application/pdf",
    )
    await service.remember(_key(), stored)

    first = await service.recall(_key())
    second = await service.recall(_key())

    assert first is not None and second is not None
    assert first.markdown_content == second.markdown_content == "# Stable\n"
