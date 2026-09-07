from sqlalchemy.orm import Session

from modules.documents.models import Document
from worker.studio.artifact import Source

# One job's grounding budget in characters. ponytail: a flat cap, not tokens,
# and no ranking — fine for summarising a handful of local documents. Upgrade
# path: document-scoped hybrid retrieval when a selection outgrows one window.
BUDGET_CHARS = 24_000


def gather(session: Session, document_ids: list[int]) -> list[Source]:
    """Load the selected documents' extracted text, capped to a context budget."""
    sources: list[Source] = []
    remaining = BUDGET_CHARS
    for document_id in document_ids:
        document = session.get(Document, document_id)
        if document is None or not document.content:
            continue
        content = document.content[:remaining]
        remaining -= len(content)
        sources.append(Source(document.id, document.title, content))
        if remaining <= 0:
            break
    return sources
