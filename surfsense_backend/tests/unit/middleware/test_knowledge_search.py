"""Unit tests for knowledge_search middleware helpers.

These test pure functions that don't require a database.
"""

import pytest

from app.agents.new_chat.middleware.knowledge_search import (
    _build_document_xml,
    _resolve_search_types,
)

pytestmark = pytest.mark.unit


# ── _resolve_search_types ──────────────────────────────────────────────


class TestResolveSearchTypes:
    def test_returns_none_when_no_inputs(self):
        assert _resolve_search_types(None, None) is None

    def test_returns_none_when_both_empty(self):
        assert _resolve_search_types([], []) is None

    def test_includes_legacy_type_for_google_gmail(self):
        result = _resolve_search_types(["GOOGLE_GMAIL_CONNECTOR"], None)
        assert "GOOGLE_GMAIL_CONNECTOR" in result
        assert "COMPOSIO_GMAIL_CONNECTOR" in result

    def test_includes_legacy_type_for_google_drive(self):
        result = _resolve_search_types(None, ["GOOGLE_DRIVE_FILE"])
        assert "GOOGLE_DRIVE_FILE" in result
        assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" in result

    def test_includes_legacy_type_for_google_calendar(self):
        result = _resolve_search_types(["GOOGLE_CALENDAR_CONNECTOR"], None)
        assert "GOOGLE_CALENDAR_CONNECTOR" in result
        assert "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR" in result

    def test_no_legacy_expansion_for_unrelated_types(self):
        result = _resolve_search_types(["FILE", "NOTE"], None)
        assert set(result) == {"FILE", "NOTE"}

    def test_combines_connectors_and_document_types(self):
        result = _resolve_search_types(["FILE"], ["NOTE", "CRAWLED_URL"])
        assert {"FILE", "NOTE", "CRAWLED_URL"}.issubset(set(result))

    def test_deduplicates(self):
        result = _resolve_search_types(["FILE", "FILE"], ["FILE"])
        assert result.count("FILE") == 1


# ── _build_document_xml ────────────────────────────────────────────────


class TestBuildDocumentXml:
    @pytest.fixture
    def sample_document(self):
        return {
            "document_id": 42,
            "document": {
                "id": 42,
                "document_type": "FILE",
                "title": "Test Doc",
                "metadata": {"url": "https://example.com"},
            },
            "chunks": [
                {"chunk_id": 101, "content": "First chunk content"},
                {"chunk_id": 102, "content": "Second chunk content"},
                {"chunk_id": 103, "content": "Third chunk content"},
            ],
        }

    def test_contains_document_metadata(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<document_id>42</document_id>" in xml
        assert "<document_type>FILE</document_type>" in xml
        assert "Test Doc" in xml

    def test_contains_chunk_index(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<chunk_index>" in xml
        assert "</chunk_index>" in xml
        assert 'chunk_id="101"' in xml
        assert 'chunk_id="102"' in xml
        assert 'chunk_id="103"' in xml

    def test_matched_chunks_flagged_in_index(self, sample_document):
        xml = _build_document_xml(sample_document, matched_chunk_ids={101, 103})
        lines = xml.split("\n")
        for line in lines:
            if 'chunk_id="101"' in line:
                assert 'matched="true"' in line
            if 'chunk_id="102"' in line:
                assert 'matched="true"' not in line
            if 'chunk_id="103"' in line:
                assert 'matched="true"' in line

    def test_chunk_content_in_document_content_section(self, sample_document):
        xml = _build_document_xml(sample_document)
        assert "<document_content>" in xml
        assert "First chunk content" in xml
        assert "Second chunk content" in xml
        assert "Third chunk content" in xml

    def test_line_numbers_in_chunk_index_are_accurate(self, sample_document):
        """Verify that the line ranges in chunk_index actually point to the right content."""
        xml = _build_document_xml(sample_document, matched_chunk_ids={101})
        xml_lines = xml.split("\n")

        for line in xml_lines:
            if 'chunk_id="101"' in line and "lines=" in line:
                import re

                m = re.search(r'lines="(\d+)-(\d+)"', line)
                assert m, f"No lines= attribute found in: {line}"
                start, _end = int(m.group(1)), int(m.group(2))
                target_line = xml_lines[start - 1]
                assert "101" in target_line
                assert "First chunk content" in target_line
                break
        else:
            pytest.fail("chunk_id=101 entry not found in chunk_index")

    def test_splits_into_lines_correctly(self, sample_document):
        """Each chunk occupies exactly one line (no embedded newlines)."""
        xml = _build_document_xml(sample_document)
        lines = xml.split("\n")
        chunk_lines = [
            line for line in lines if "<![CDATA[" in line and "<chunk" in line
        ]
        assert len(chunk_lines) == 3
