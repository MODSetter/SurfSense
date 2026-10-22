"""What a source pulled from a link keeps of it, in `document_metadata`."""

from typing import Any

from modules.documents.models import Document, DocumentType

SOURCE_URL = "source_url"
PULLER = "puller"


def link_metadata(url: str, puller_id: str, plugin_id: str) -> dict[str, Any]:
    return {SOURCE_URL: url, PULLER: puller_id, "plugin_id": plugin_id}


def awaiting_pull(document: Document) -> bool:
    """A link's source whose pull has not written it yet: Retry pulls it again."""
    metadata = document.document_metadata or {}
    return (
        document.document_type == DocumentType.NOTE
        and PULLER in metadata
        and document.content is None
    )
