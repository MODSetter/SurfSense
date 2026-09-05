import re
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

# Each leg proposes this many for recall; the cosine rescore then orders the union.
CANDIDATES = 20

_WORD = re.compile(r"\w+")
_COLUMNS = "c.id, c.document_id, c.content, c.start_line, c.end_line"


@dataclass(frozen=True)
class Hit:
    """A chunk a query reached, and where it sits."""

    chunk_id: int
    document_id: int
    content: str
    start_line: int | None
    end_line: int | None
    score: float


def retrieve(
    session: Session, workspace_id: int, query: str, top_k: int = 5
) -> list[Hit]:
    """Rank a workspace's chunks against a query.

    A keyword leg (FTS5 BM25) and a semantic leg (sqlite-vec nearest neighbour)
    each widen recall; their union is then rescored by cosine similarity to the
    query, so meaning decides the order and keyword matches only add reach.
    """
    if not query.strip():
        return []

    # Lazy: pulls onnxruntime and the model, which only chat and ingest need.
    from sqlite_vec import serialize_float32

    from worker.ingestion.embedding import embed

    vector = serialize_float32(embed([query])[0])
    candidates = _keyword_leg(session, workspace_id, query) | _vector_leg(
        session, workspace_id, vector
    )
    if not candidates:
        return []

    return _rank_by_similarity(session, candidates, vector, top_k)


def _keyword_leg(session: Session, workspace_id: int, query: str) -> set[int]:
    terms = _WORD.findall(query.lower())
    if not terms:
        return set()

    # Quote each term against FTS5's grammar; OR keeps recall wide.
    match = " OR ".join(f'"{term}"' for term in terms)
    rows = session.execute(
        text(
            "SELECT c.id FROM chunks_fts "
            "JOIN chunks c ON c.id = chunks_fts.rowid "
            "JOIN documents d ON d.id = c.document_id "
            "WHERE chunks_fts MATCH :match AND d.workspace_id = :ws "
            "ORDER BY bm25(chunks_fts) LIMIT :k"
        ),
        {"match": match, "ws": workspace_id, "k": CANDIDATES},
    )
    return {row[0] for row in rows}


def _vector_leg(session: Session, workspace_id: int, vector: bytes) -> set[int]:
    # KNN scans the whole index (its own CTE, as vec0 wants), then the workspace
    # filter applies. ponytail: fine for a few small local workspaces; widen k if
    # a workspace's hits start falling outside the global top CANDIDATES.
    rows = session.execute(
        text(
            "WITH knn AS ("
            "  SELECT rowid FROM chunk_vectors WHERE embedding MATCH :vector AND k = :k"
            ") "
            "SELECT c.id FROM knn "
            "JOIN chunks c ON c.id = knn.rowid "
            "JOIN documents d ON d.id = c.document_id "
            "WHERE d.workspace_id = :ws"
        ),
        {"vector": vector, "k": CANDIDATES, "ws": workspace_id},
    )
    return {row[0] for row in rows}


def _rank_by_similarity(
    session: Session, candidates: set[int], vector: bytes, top_k: int
) -> list[Hit]:
    stmt = text(
        f"SELECT {_COLUMNS}, "
        "vec_distance_cosine(v.embedding, :vector) AS distance "
        "FROM chunks c JOIN chunk_vectors v ON v.rowid = c.id "
        "WHERE c.id IN :ids ORDER BY distance LIMIT :k"
    ).bindparams(bindparam("ids", expanding=True))
    rows = session.execute(
        stmt, {"vector": vector, "ids": list(candidates), "k": top_k}
    )
    return [
        Hit(
            chunk_id=row.id,
            document_id=row.document_id,
            content=row.content,
            start_line=row.start_line,
            end_line=row.end_line,
            score=1.0 - row.distance,
        )
        for row in rows
    ]
