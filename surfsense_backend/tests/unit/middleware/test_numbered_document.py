"""Unit tests for the numbered-document read preamble."""

import pytest

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.numbered_document import (
    build_read_preamble,
    compute_matched_line_ranges,
)

pytestmark = pytest.mark.unit


_BODY = "alpha\nbravo\ncharlie\ndelta"


class TestComputeMatchedLineRanges:
    def test_maps_matched_chunk_spans_to_line_ranges(self):
        chunks = [(1, 0, 12), (2, 12, len(_BODY))]
        ranges = compute_matched_line_ranges(_BODY, chunks, {2})
        assert ranges == [(3, 4)]

    def test_includes_only_matched_chunks(self):
        chunks = [(1, 0, 5), (2, 6, 11)]
        ranges = compute_matched_line_ranges(_BODY, chunks, {1})
        assert ranges == [(1, 1)]

    def test_skips_chunks_without_spans(self):
        chunks = [(1, None, None)]
        ranges = compute_matched_line_ranges(_BODY, chunks, {1})
        assert ranges == []

    def test_sorted_and_deduplicated(self):
        chunks = [(1, 12, len(_BODY)), (2, 0, 5), (3, 0, 5)]
        ranges = compute_matched_line_ranges(_BODY, chunks, {1, 2, 3})
        assert ranges == [(1, 1), (3, 4)]


class TestBuildReadPreamble:
    def test_contains_document_metadata(self):
        preamble = build_read_preamble(
            document_id=42,
            document_type="FILE",
            title="Test Doc",
            url="https://example.com",
            matched_line_ranges=[],
        )
        assert "<document_id>42</document_id>" in preamble
        assert "<document_type>FILE</document_type>" in preamble
        assert "Test Doc" in preamble
        assert "https://example.com" in preamble

    def test_citation_hint_uses_document_id(self):
        preamble = build_read_preamble(
            document_id=42,
            document_type="FILE",
            title="Test Doc",
            url="",
            matched_line_ranges=[],
        )
        assert "[citation:d42#L" in preamble

    def test_lists_matched_line_ranges(self):
        preamble = build_read_preamble(
            document_id=7,
            document_type="NOTE",
            title="Notes",
            url="",
            matched_line_ranges=[(12, 18), (40, 40)],
        )
        assert "<matched_lines>" in preamble
        assert "12-18" in preamble
        assert "40" in preamble

    def test_omits_matched_lines_block_when_empty(self):
        preamble = build_read_preamble(
            document_id=7,
            document_type="NOTE",
            title="Notes",
            url="",
            matched_line_ranges=[],
        )
        assert "<matched_lines>" not in preamble

    def test_ends_with_trailing_newline_so_body_follows_cleanly(self):
        preamble = build_read_preamble(
            document_id=1,
            document_type="FILE",
            title="t",
            url="",
            matched_line_ranges=[],
        )
        assert preamble.endswith("\n")
