"""MarkdownCacheStore against a real local filesystem backend (no mocks).

Proves the blob side of the cache: markdown written under a content-addressed key
comes back byte-for-byte, and a delete actually removes it.
"""

from __future__ import annotations

import pytest

from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.storage import MarkdownCacheStore
from app.etl_pipeline.cache.storage.object_keys import build_parse_object_key

pytestmark = pytest.mark.integration


def _key() -> ParseKey:
    return ParseKey.for_document(
        "d" * 64, etl_service="LLAMACLOUD", mode="basic", version=1
    )


async def test_save_then_load_round_trips_markdown(cache_local_storage):
    store = MarkdownCacheStore()
    markdown = "# Title\n\nBody with unicode: café, naïve, 漢字.\n"

    storage_key = await store.save(_key(), markdown)

    assert storage_key == build_parse_object_key(_key())
    assert await store.load(storage_key) == markdown


async def test_delete_removes_the_blob(cache_local_storage):
    store = MarkdownCacheStore()
    storage_key = await store.save(_key(), "to be deleted")

    await store.delete(storage_key)

    # Eviction deleted the blob; a later read must fail rather than serve stale.
    with pytest.raises(FileNotFoundError):
        await store.load(storage_key)
