"""extract_with_cache end-to-end: real DB + real local storage.

The only seam mocked is the parser itself (``EtlPipelineService.extract``) -- the
external boundary the facade wraps. Everything else (eligibility, hashing, recall,
remember, blob I/O) runs for real, so these tests prove the actual cost saving:
identical bytes are parsed once and reused.
"""

from __future__ import annotations

import pytest

from app.config import config
from app.etl_pipeline.cache.cached_extraction import extract_with_cache
from app.etl_pipeline.etl_document import EtlRequest, EtlResult, ProcessingMode

pytestmark = pytest.mark.integration


class _CountingParser:
    """Stand-in for the external parser; records how often it actually ran."""

    def __init__(self, **_kwargs) -> None:
        pass

    calls = 0

    async def extract(self, request: EtlRequest) -> EtlResult:
        type(self).calls += 1
        return EtlResult(
            markdown_content="# Parsed once\n",
            etl_service="LLAMACLOUD",
            actual_pages=3,
            content_type="application/pdf",
        )


@pytest.fixture
def counting_parser(monkeypatch):
    _CountingParser.calls = 0
    monkeypatch.setattr(
        "app.etl_pipeline.cache.cached_extraction.EtlPipelineService",
        _CountingParser,
    )
    return _CountingParser


async def test_identical_uploads_are_parsed_once_then_served_from_cache(
    tmp_path, monkeypatch, counting_parser, cache_local_storage, clean_cache_table
):
    monkeypatch.setattr(config, "ETL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "ETL_SERVICE", "LLAMACLOUD")

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 unique-bytes-for-this-test")
    request = EtlRequest(
        file_path=str(pdf), filename="doc.pdf", processing_mode=ProcessingMode.BASIC
    )

    first = await extract_with_cache(request)
    second = await extract_with_cache(request)

    assert counting_parser.calls == 1  # second upload reused the cache
    assert first.markdown_content == second.markdown_content == "# Parsed once\n"
    assert second.actual_pages == 3
    assert second.content_type == "application/pdf"


async def test_disabled_cache_parses_every_time(
    tmp_path, monkeypatch, counting_parser
):
    monkeypatch.setattr(config, "ETL_CACHE_ENABLED", False)
    monkeypatch.setattr(config, "ETL_SERVICE", "LLAMACLOUD")

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 another-unique-payload")
    request = EtlRequest(
        file_path=str(pdf), filename="doc.pdf", processing_mode=ProcessingMode.BASIC
    )

    await extract_with_cache(request)
    await extract_with_cache(request)

    assert counting_parser.calls == 2  # bypassed: no reuse
