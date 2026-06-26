import hashlib

from app.indexing_pipeline.connector_document import ConnectorDocument


def compute_identifier_hash(
    document_type_value: str, unique_id: str, workspace_id: int
) -> str:
    """Return a stable SHA-256 hash from raw identity components."""
    combined = f"{document_type_value}:{unique_id}:{workspace_id}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_unique_identifier_hash(doc: ConnectorDocument) -> str:
    """Return a stable SHA-256 hash identifying a document by its source identity."""
    return compute_identifier_hash(
        doc.document_type.value, doc.unique_id, doc.workspace_id
    )


def compute_content_hash(doc: ConnectorDocument) -> str:
    """Return a SHA-256 hash of the document's content scoped to its workspace."""
    combined = f"{doc.workspace_id}:{doc.source_markdown}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
