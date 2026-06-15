"""Gating rule: may this upload be served from / written to the parse cache?"""

from __future__ import annotations

from app.etl_pipeline.file_classifier import FileCategory, classify_file


def is_parse_cacheable(
    *,
    filename: str,
    etl_service: str | None,
    cache_enabled: bool,
    has_vision_llm: bool,
) -> bool:
    """Only deterministic document parses are shareable across workspaces.

    Vision-LLM runs append model-generated content not captured by the cache key,
    and a missing ETL service means there is no document parser to key against --
    both bypass the cache. Non-document categories (plaintext, audio, images,
    direct-convert) are cheap or parser-agnostic and are handled outside it.
    """
    if not cache_enabled:
        return False
    if has_vision_llm:
        return False
    if not etl_service:
        return False
    return classify_file(filename) == FileCategory.DOCUMENT
