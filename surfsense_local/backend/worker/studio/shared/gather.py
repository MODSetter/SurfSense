from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.chunks.models import Chunk
from modules.documents.models import Document
from shared import search
from worker.studio.shared.artifact import Source

# One job's grounding budget in characters. ponytail: a flat cap, not tokens.
# Ceiling: fine while one window holds it; count tokens if prompts start to overflow.
BUDGET_CHARS = 24_000

# Between two passages of one document that were not next to each other.
GAP = "\n\n[...]\n\n"


def gather(
    session: Session, document_ids: list[int], query: str | None = None
) -> list[Source]:
    """The selected documents' text, cut to the budget.

    A selection that fits is sent whole. One that does not gives every document
    an even share, so none is left out; with a `query`, each share holds that
    document's passages that best match it, else the document's start.
    """
    documents = [
        document
        for document_id in document_ids
        if (document := session.get(Document, document_id)) and document.content
    ]
    if sum(len(document.content) for document in documents) <= BUDGET_CHARS:
        return [Source(d.id, d.title, d.content) for d in documents]

    shares = _shares([len(document.content) for document in documents])
    passages = _passages(session, documents, query) if query and query.strip() else {}
    return [
        Source(
            document.id,
            document.title,
            _excerpt(session, document.content, share, passages.get(document.id, [])),
        )
        for document, share in zip(documents, shares, strict=True)
    ]


def _shares(lengths: list[int]) -> list[int]:
    """The budget split evenly, a short document's unused part going to the rest."""
    shares = [0] * len(lengths)
    remaining, left = BUDGET_CHARS, len(lengths)
    for index in sorted(range(len(lengths)), key=lengths.__getitem__):
        shares[index] = min(lengths[index], remaining // left)
        remaining -= shares[index]
        left -= 1
    return shares


def _passages(
    session: Session, documents: list[Document], query: str
) -> dict[int, list[search.Hit]]:
    """Each document's chunks matching the query, best first, from one search."""
    hits = search.retrieve(
        session,
        documents[0].workspace_id,
        query,
        top_k=2 * search.CANDIDATES,
        document_ids=[document.id for document in documents],
    )
    by_document: dict[int, list[search.Hit]] = {}
    for hit in hits:
        by_document.setdefault(hit.document_id, []).append(hit)
    return by_document


def _excerpt(session: Session, content: str, share: int, hits: list[search.Hit]) -> str:
    """The best-matching passages that fit the share, in reading order; the
    document's start where none matched."""
    chosen: list[search.Hit] = []
    used = 0
    for hit in hits:
        # Priced at the gap, the dearer join, so the share holds either way.
        cost = len(hit.content) + (len(GAP) if chosen else 0)
        if used + cost > share:
            continue
        chosen.append(hit)
        used += cost
    if not chosen:
        return content[:share]

    positions = dict(
        session.execute(
            select(Chunk.id, Chunk.position).where(
                Chunk.id.in_([hit.chunk_id for hit in chosen])
            )
        ).all()
    )
    chosen.sort(key=lambda hit: positions[hit.chunk_id])
    excerpt = chosen[0].content
    for before, hit in pairwise(chosen):
        adjacent = positions[hit.chunk_id] == positions[before.chunk_id] + 1
        excerpt += ("\n\n" if adjacent else GAP) + hit.content
    return excerpt
