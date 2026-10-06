from itertools import pairwise

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.chunks.models import Chunk
from modules.documents.models import Document
from shared import search
from worker.studio.shared.artifact import Source

# One job's grounding budget in characters, unless the model's profile sets one.
# ponytail: a flat cap, not tokens. Ceiling: fine while one window holds it;
# count tokens if prompts start to overflow.
BUDGET_CHARS = 24_000

# Below this even share a document says nothing, so the scope's best passages
# are taken instead. An estimate: about one 480-token chunk.
MIN_SHARE_CHARS = 1_500

# What to search for when neither the prompt nor the format names a focus.
DEFAULT_FOCUS = "the main points, findings, figures and conclusions"

# Between two passages of one document that were not next to each other.
GAP = "\n\n[...]\n\n"


def gather(
    session: Session,
    document_ids: list[int],
    query: str | None = None,
    *,
    budget_chars: int | None = None,
    focus: str | None = None,
) -> list[Source]:
    """The selected documents' text, cut to the budget.

    A selection that fits is sent whole. One that does not gives every document
    an even share, so none is left out; with a `query`, each share holds that
    document's passages that best match it, else the document's start. When the
    share would fall below `MIN_SHARE_CHARS`, the selection's best passages for
    the query, else `focus`, are taken instead, and only documents holding one
    are returned: the caller records those as what the job was grounded on.
    """
    budget = budget_chars or BUDGET_CHARS
    lengths = dict(
        session.execute(
            select(Document.id, func.length(Document.content)).where(
                Document.id.in_(document_ids), Document.content.is_not(None)
            )
        ).all()
    )
    chosen_ids = [i for i in dict.fromkeys(document_ids) if lengths.get(i)]
    if not chosen_ids:
        return []
    if sum(lengths[i] for i in chosen_ids) > budget and (
        budget // len(chosen_ids) < MIN_SHARE_CHARS
    ):
        search_for = query if query and query.strip() else focus or DEFAULT_FOCUS
        return _best_passages(session, chosen_ids, search_for, budget)

    documents = [session.get(Document, i) for i in chosen_ids]
    documents = [d for d in documents if d is not None and d.content]
    if sum(len(document.content) for document in documents) <= budget:
        return [Source(d.id, d.title, d.content) for d in documents]

    shares = _shares([len(document.content) for document in documents], budget)
    passages = _passages(session, documents, query) if query and query.strip() else {}
    return [
        Source(
            document.id,
            document.title,
            _excerpt(session, document.content, share, passages.get(document.id, [])),
        )
        for document, share in zip(documents, shares, strict=True)
    ]


def _best_passages(
    session: Session, document_ids: list[int], query: str, budget: int
) -> list[Source]:
    """The selection's best-matching passages that fit the budget, grouped by
    document in selection order and in reading order within each."""
    workspace_id = session.scalar(
        select(Document.workspace_id).where(Document.id == document_ids[0])
    )
    hits = search.retrieve(
        session,
        workspace_id,
        query,
        top_k=max(1, budget // MIN_SHARE_CHARS),
        document_ids=document_ids,
    )
    by_document: dict[int, list[search.Hit]] = {}
    used = 0
    for hit in hits:
        # Priced at the gap, the dearer join, so the budget holds either way.
        cost = len(hit.content) + len(GAP)
        if used + cost > budget:
            continue
        by_document.setdefault(hit.document_id, []).append(hit)
        used += cost
    positions = dict(
        session.execute(
            select(Chunk.id, Chunk.position).where(
                Chunk.id.in_([h.chunk_id for hs in by_document.values() for h in hs])
            )
        ).all()
    )
    sources = []
    for document_id in document_ids:
        chosen = sorted(
            by_document.get(document_id, []), key=lambda h: positions[h.chunk_id]
        )
        if chosen:
            sources.append(
                Source(document_id, chosen[0].title, _joined(chosen, positions))
            )
    return sources


def _shares(lengths: list[int], budget: int) -> list[int]:
    """The budget split evenly, a short document's unused part going to the rest."""
    shares = [0] * len(lengths)
    remaining, left = budget, len(lengths)
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
    return _joined(chosen, positions)


def _joined(chosen: list[search.Hit], positions: dict[int, int]) -> str:
    """Passages in reading order, marking where text between them was left out."""
    excerpt = chosen[0].content
    for before, hit in pairwise(chosen):
        adjacent = positions[hit.chunk_id] == positions[before.chunk_id] + 1
        excerpt += ("\n\n" if adjacent else GAP) + hit.content
    return excerpt
