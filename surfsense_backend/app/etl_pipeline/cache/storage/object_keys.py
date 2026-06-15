"""Object keys for cached markdown, namespaced under a dedicated prefix."""

from __future__ import annotations

from app.etl_pipeline.cache.schemas import ParseKey

CACHE_PREFIX = "etl_cache"


def build_parse_object_key(key: ParseKey) -> str:
    # Content-addressed: identical bytes + recipe always map to the same key.
    return f"{CACHE_PREFIX}/{key.source_sha256}/{key.object_suffix}"
