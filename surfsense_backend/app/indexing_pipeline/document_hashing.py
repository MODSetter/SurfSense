import hashlib

from app.indexing_pipeline.connector_document import ConnectorDocument


def compute_unique_identifier_hash(doc: ConnectorDocument) -> str:
    """Return a stable SHA-256 hash identifying a document by its source identity."""
    combined = f"{doc.document_type.value}:{doc.unique_id}:{doc.search_space_id}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_content_hash(doc: ConnectorDocument) -> str:
    """Return a SHA-256 hash of the document's content scoped to its search space."""
    combined = f"{doc.search_space_id}:{doc.source_markdown}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
