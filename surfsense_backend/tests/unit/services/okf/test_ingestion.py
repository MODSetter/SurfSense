"""A ConnectorDocument (the indexing write door) must serialize to a valid OKF
concept. Per-``DocumentType`` conformance lives in ``test_conformance.py``.
"""

from app.db import Document, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.services.okf import document_to_concept, is_conformant_concept


def _document_from(connector_doc: ConnectorDocument) -> Document:
    """Mirror how prepare_for_indexing builds a Document from a ConnectorDocument."""
    return Document(
        title=connector_doc.title,
        document_type=connector_doc.document_type,
        source_markdown=connector_doc.source_markdown,
        document_metadata=connector_doc.metadata,
    )


def test_minimal_connector_document_yields_conformant_concept() -> None:
    connector_doc = ConnectorDocument(
        title="Bare",
        source_markdown="just a body",
        unique_id="u1",
        document_type=DocumentType.FILE,
        workspace_id=1,
        created_by_id="user-1",
    )
    doc = _document_from(connector_doc)
    concept = document_to_concept(doc, body=doc.source_markdown)
    assert is_conformant_concept(concept)
