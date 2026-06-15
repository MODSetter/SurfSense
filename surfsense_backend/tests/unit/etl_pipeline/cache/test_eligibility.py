"""What is allowed into the cache -- the gating rules, as pure logic.

These rules decide whether a given upload may be served from / written to the
parse cache. They live in a pure predicate so every branch (disabled, vision,
no service, file category) is covered here without touching DB, storage, or the
parser.
"""

from __future__ import annotations

import pytest

from app.etl_pipeline.cache.eligibility import is_parse_cacheable

pytestmark = pytest.mark.unit


def test_document_with_service_and_cache_on_is_cacheable():
    assert is_parse_cacheable(
        filename="report.pdf",
        etl_service="LLAMACLOUD",
        cache_enabled=True,
        has_vision_llm=False,
    )


def test_disabled_cache_is_never_cacheable():
    assert not is_parse_cacheable(
        filename="report.pdf",
        etl_service="LLAMACLOUD",
        cache_enabled=False,
        has_vision_llm=False,
    )


def test_vision_llm_run_is_not_cacheable():
    # Vision appends model output not captured by the key; sharing it would leak
    # one run's generated text into a plain parse of the same bytes.
    assert not is_parse_cacheable(
        filename="report.pdf",
        etl_service="LLAMACLOUD",
        cache_enabled=True,
        has_vision_llm=True,
    )


@pytest.mark.parametrize("etl_service", [None, ""])
def test_missing_etl_service_is_not_cacheable(etl_service):
    assert not is_parse_cacheable(
        filename="report.pdf",
        etl_service=etl_service,
        cache_enabled=True,
        has_vision_llm=False,
    )


@pytest.mark.parametrize(
    "filename",
    ["paper.pdf", "memo.docx", "slides.pptx", "sheet.xlsx", "book.epub"],
)
def test_document_extensions_are_cacheable(filename):
    assert is_parse_cacheable(
        filename=filename,
        etl_service="LLAMACLOUD",
        cache_enabled=True,
        has_vision_llm=False,
    )


@pytest.mark.parametrize(
    "filename",
    [
        "notes.txt",  # plaintext
        "readme.md",  # plaintext
        "main.py",  # plaintext
        "podcast.mp3",  # audio
        "photo.png",  # image (vision path / fallback, not a shared doc parse)
        "data.csv",  # direct-convert
        "archive.xyz",  # unsupported
    ],
)
def test_non_document_categories_are_not_cacheable(filename):
    assert not is_parse_cacheable(
        filename=filename,
        etl_service="LLAMACLOUD",
        cache_enabled=True,
        has_vision_llm=False,
    )
