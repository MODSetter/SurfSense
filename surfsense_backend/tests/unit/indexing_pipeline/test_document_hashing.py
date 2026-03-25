import pytest

from app.db import DocumentType
from app.indexing_pipeline.document_hashing import (
    compute_content_hash,
    compute_identifier_hash,
    compute_unique_identifier_hash,
)

pytestmark = pytest.mark.unit


def test_different_unique_id_produces_different_hash(make_connector_document):
    """Two documents with different unique_ids produce different identifier hashes."""
    doc_a = make_connector_document(unique_id="id-001")
    doc_b = make_connector_document(unique_id="id-002")
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(
        doc_b
    )


def test_different_search_space_produces_different_identifier_hash(
    make_connector_document,
):
    """Same document in different search spaces produces different identifier hashes."""
    doc_a = make_connector_document(search_space_id=1)
    doc_b = make_connector_document(search_space_id=2)
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(
        doc_b
    )


def test_different_document_type_produces_different_identifier_hash(
    make_connector_document,
):
    """Same unique_id with different document types produces different identifier hashes."""
    doc_a = make_connector_document(document_type=DocumentType.CLICKUP_CONNECTOR)
    doc_b = make_connector_document(document_type=DocumentType.NOTION_CONNECTOR)
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(
        doc_b
    )


def test_same_content_same_space_produces_same_content_hash(make_connector_document):
    """Identical content in the same search space always produces the same content hash."""
    doc_a = make_connector_document(source_markdown="Hello world", search_space_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", search_space_id=1)
    assert compute_content_hash(doc_a) == compute_content_hash(doc_b)


def test_same_content_different_space_produces_different_content_hash(
    make_connector_document,
):
    """Identical content in different search spaces produces different content hashes."""
    doc_a = make_connector_document(source_markdown="Hello world", search_space_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", search_space_id=2)
    assert compute_content_hash(doc_a) != compute_content_hash(doc_b)


def test_different_content_produces_different_content_hash(make_connector_document):
    """Different source markdown produces different content hashes."""
    doc_a = make_connector_document(source_markdown="Original content")
    doc_b = make_connector_document(source_markdown="Updated content")
    assert compute_content_hash(doc_a) != compute_content_hash(doc_b)


def test_compute_identifier_hash_matches_connector_doc_hash(make_connector_document):
    """Raw-args hash equals ConnectorDocument hash for equivalent inputs."""
    doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-123",
        search_space_id=5,
    )
    raw_hash = compute_identifier_hash("GOOGLE_GMAIL_CONNECTOR", "msg-123", 5)
    assert raw_hash == compute_unique_identifier_hash(doc)


def test_compute_identifier_hash_differs_for_different_inputs():
    """Different arguments produce different hashes."""
    h1 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 1)
    h2 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-2", 1)
    h3 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 2)
    h4 = compute_identifier_hash("COMPOSIO_GOOGLE_DRIVE_CONNECTOR", "file-1", 1)
    assert len({h1, h2, h3, h4}) == 4
