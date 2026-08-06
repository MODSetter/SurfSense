import pytest

from app.db import DocumentType
from app.indexing_pipeline.document_hashing import (
    compute_content_hash,
    compute_identifier_hash,
    compute_unique_identifier_hash,
)
from app.utils.document_converters import generate_unique_identifier_hash

pytestmark = pytest.mark.unit


def test_different_unique_id_produces_different_hash(make_connector_document):
    """Two documents with different unique_ids produce different identifier hashes."""
    doc_a = make_connector_document(unique_id="id-001")
    doc_b = make_connector_document(unique_id="id-002")
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(
        doc_b
    )


def test_different_workspace_produces_different_identifier_hash(
    make_connector_document,
):
    """Same document in different workspaces produces different identifier hashes."""
    doc_a = make_connector_document(workspace_id=1)
    doc_b = make_connector_document(workspace_id=2)
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
    """Identical content in the same workspace always produces the same content hash."""
    doc_a = make_connector_document(source_markdown="Hello world", workspace_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", workspace_id=1)
    assert compute_content_hash(doc_a) == compute_content_hash(doc_b)


def test_same_content_different_space_produces_different_content_hash(
    make_connector_document,
):
    """Identical content in different workspaces produces different content hashes."""
    doc_a = make_connector_document(source_markdown="Hello world", workspace_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", workspace_id=2)
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
        workspace_id=5,
    )
    raw_hash = compute_identifier_hash("GOOGLE_GMAIL_CONNECTOR", "msg-123", 5)
    assert raw_hash == compute_unique_identifier_hash(doc)


def test_a_note_dto_hashes_the_same_as_a_row_at_that_virtual_path(
    make_connector_document,
):
    """The seam the store indexer is built on: two formulas, two modules.

    ``compute_identifier_hash`` here and ``generate_unique_identifier_hash`` in
    ``utils.document_converters`` independently build ``{type}:{id}:{workspace}``.
    The indexer hands the pipeline a synthetic NOTE DTO keyed on a virtual path
    and looks the row up by the other function's hash, so if the two ever drift
    every git-indexed document silently forks into two identities.
    """
    virtual_path = "/documents/notes/Meeting.xml"
    doc = make_connector_document(
        document_type=DocumentType.NOTE,
        unique_id=virtual_path,
        workspace_id=7,
    )

    assert compute_unique_identifier_hash(doc) == generate_unique_identifier_hash(
        DocumentType.NOTE, virtual_path, 7
    )


def test_compute_identifier_hash_differs_for_different_inputs():
    """Different arguments produce different hashes."""
    h1 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 1)
    h2 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-2", 1)
    h3 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 2)
    h4 = compute_identifier_hash("COMPOSIO_GOOGLE_DRIVE_CONNECTOR", "file-1", 1)
    assert len({h1, h2, h3, h4}) == 4
