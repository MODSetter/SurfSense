"""A pending note per link, at the top of the Library, until its pull writes it."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentType
from modules.documents.web_sources.background_pull.source_link import (
    SOURCE_URL,
    link_metadata,
)
from modules.documents.web_sources.pullers.puller import Puller
from modules.source_roots.managed_root import ensure_managed_root


def sources_of_links(
    session: Session, workspace_id: int, urls: list[str]
) -> dict[str, int]:
    """Each link already in Sources, to its note, wherever the user filed it since."""
    source_url = func.json_extract(Document.document_metadata, f"$.{SOURCE_URL}")
    rows = session.execute(
        select(source_url, Document.id).where(
            Document.workspace_id == workspace_id,
            Document.document_type == DocumentType.NOTE,
            source_url.in_(urls),
        )
    )
    return dict(rows.tuples().all())


def pending_sources(
    session: Session, workspace_id: int, links: list[tuple[str, Puller]]
) -> list[Document]:
    """Titled by the link until the pull finds the page's own title."""
    folder_id = ensure_managed_root(session, workspace_id).id
    notes = [
        Document(
            workspace_id=workspace_id,
            title=url[:500],
            document_type=DocumentType.NOTE,
            content=None,
            document_metadata=link_metadata(url, puller.id, puller.plugin_id),
            folder_id=folder_id,
        )
        for url, puller in links
    ]
    session.add_all(notes)
    session.flush()
    return notes
