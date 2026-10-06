"""A render without artifact_id titled like a document its thread already rendered, in the same format, is refused.

Weaker models left artifact_id out of edits, so a change became a second
document (Gemma 4 31B in 5 of 18 ladder runs, 08-model-ladder-results). Another
format under the same title is a new document ("now a PDF version").
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS
from modules.documents.models import Document, DocumentStatus

# A failed or cancelled version is no document the user has.
_KEPT = (DocumentStatus.PENDING, DocumentStatus.PROCESSING, DocumentStatus.READY)


def refuse_same_title(
    session: Session, thread_id: int, title: str, format: object
) -> None:
    """Refuse a new document whose title and format match one the thread rendered."""
    if format not in DOCUMENT_FORMATS:
        return  # the service refuses it, naming the formats
    wanted = _key(title)
    rendered = session.execute(
        select(Artifact.id, Document.title)
        .join(Document, Artifact.document_id == Document.id)
        .where(
            Artifact.chat_thread_id == thread_id,
            Artifact.format == format,
            Document.status.in_(_KEPT),
        )
        .order_by(Artifact.id.desc())
    ).all()
    session.rollback()  # a read only; the version is made in its own transaction
    for artifact_id, existing in rendered:
        if _key(existing) == wanted:
            raise ToolCallError(
                f'This chat already rendered "{existing}" as artifact {artifact_id}: '
                f"pass artifact_id {artifact_id} to change it, or give a new "
                "document a different title."
            )


def _key(title: str) -> str:
    return "".join(title.split()).casefold()
