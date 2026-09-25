import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

# Each leg proposes this many for recall; the blend below orders the union.
CANDIDATES = 20

_WORD = re.compile(r"\w+")
_COLUMNS = "c.id, c.document_id, d.title, c.content, c.start_line, c.end_line"


@dataclass(frozen=True)
class Hit:
    """A chunk a query reached, and where it sits."""

    chunk_id: int
    document_id: int
    content: str
    start_line: int | None
    end_line: int | None
    score: float
    title: str = ""


def retrieve(
    session: Session,
    workspace_id: int,
    query: str,
    top_k: int = 5,
    document_ids: Sequence[int] | None = None,
) -> list[Hit]:
    """Rank a workspace's chunks against a query.

    A keyword leg (FTS5 BM25) and a semantic leg (sqlite-vec nearest neighbour)
    each propose candidates, and a weighted blend of both decides the order.
    Meaning alone used to decide it, which left an exact term findable only
    where the embedder happened to agree: a bare asset tag returned manuals in
    other languages while the document holding it ranked nowhere.
    """
    if not query.strip() or (document_ids is not None and not document_ids):
        return []

    selected_document_ids = (
        tuple(dict.fromkeys(document_ids)) if document_ids is not None else None
    )

    # Lazy: pulls onnxruntime and the model, which only chat and ingest need.
    from sqlite_vec import serialize_float32

    from worker.ingestion.embedding import embed

    vector = serialize_float32(embed([query])[0])
    keyword = _keyword_leg(session, workspace_id, query, selected_document_ids)
    semantic = _vector_leg(session, workspace_id, vector, selected_document_ids)
    fused = _fuse(keyword, semantic)
    if not fused:
        return []

    return _best(session, fused, vector, top_k)


# How much of the order meaning owns. Our corpus is flat across 0.6 to 0.65 and
# falls away either side, so this is the middle of a measured plateau rather
# than a default: 98% of answers reach the top 5, against 50% for meaning alone.
# Reciprocal rank fusion was tried first and rejected at 88%; throwing away each
# leg's strength let a passage sharing only "a" and "in" with the query outrank
# the one that meant the same thing, because appearing in both legs beats
# topping one.
SEMANTIC_WEIGHT = 0.65


def _fuse(
    keyword: Sequence[tuple[int, float]], semantic: Sequence[tuple[int, float]]
) -> dict[int, float]:
    """Blend the legs, each already on its own absolute 0..1 scale.

    Absolute matters more than the weight: a leg scaled against its own best
    candidate calls that candidate perfect however bad it is, so a query whose
    only keyword match is "a" would vote at full strength for nonsense. Term
    coverage and cosine both mean something on their own, so neither leg can
    inflate itself when it has nothing.
    """
    scores: dict[int, float] = {}
    for leg, weight in ((semantic, SEMANTIC_WEIGHT), (keyword, 1.0 - SEMANTIC_WEIGHT)):
        for chunk_id, strength in leg:
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight * strength
    return scores


def _keyword_leg(
    session: Session,
    workspace_id: int,
    query: str,
    document_ids: Sequence[int] | None,
) -> list[tuple[int, float]]:
    terms = _WORD.findall(query.lower())
    if not terms:
        return []

    # Quote each term against FTS5's grammar; OR keeps recall wide.
    candidates = _matching(
        session, workspace_id, " OR ".join(f'"{term}"' for term in terms), document_ids
    )
    if not candidates:
        return []

    # How much of the question a chunk answers lexically, which BM25 cannot say:
    # its scores only rank one query's candidates against each other, so its best
    # is 1.0 whether it matched every term or only "the". Coverage is comparable
    # across queries, which is what lets this leg abstain instead of guessing.
    # ponytail: one small indexed lookup per distinct term, so a long question
    # costs a few more. Move to an fts5vocab table if queries ever get long.
    covered = dict.fromkeys(candidates, 0)
    for term in set(terms):
        for chunk_id in _matching(
            session, workspace_id, f'"{term}"', document_ids, within=candidates
        ):
            covered[chunk_id] += 1
    distinct = len(set(terms))
    return [(chunk_id, count / distinct) for chunk_id, count in covered.items()]


def _matching(
    session: Session,
    workspace_id: int,
    match: str,
    document_ids: Sequence[int] | None,
    within: Sequence[int] | None = None,
) -> list[int]:
    """The workspace's chunks matching an FTS5 expression, best BM25 first."""
    sql = (
        "SELECT c.id FROM chunks_fts "
        "JOIN chunks c ON c.id = chunks_fts.rowid "
        "JOIN documents d ON d.id = c.document_id "
        "WHERE chunks_fts MATCH :match AND d.workspace_id = :ws "
    )
    params: dict[str, object] = {"match": match, "ws": workspace_id, "k": CANDIDATES}
    expanding = []
    if document_ids is not None:
        sql += "AND c.document_id IN :document_ids "
        params["document_ids"] = list(document_ids)
        expanding.append(bindparam("document_ids", expanding=True))
    if within is not None:
        sql += "AND c.id IN :within "
        params["within"] = list(within)
        expanding.append(bindparam("within", expanding=True))
    sql += "ORDER BY bm25(chunks_fts) LIMIT :k"
    statement = text(sql).bindparams(*expanding) if expanding else text(sql)
    return [row[0] for row in session.execute(statement, params)]


def _vector_leg(
    session: Session,
    workspace_id: int,
    vector: bytes,
    document_ids: Sequence[int] | None,
) -> list[tuple[int, float]]:
    # KNN scans the whole index (its own CTE, as vec0 wants), then the workspace
    # filter applies. ponytail: fine for a few small local workspaces; widen k if
    # a workspace's hits start falling outside the global top CANDIDATES.
    sql = (
        "WITH knn AS ("
        "  SELECT rowid, distance FROM chunk_vectors "
        "  WHERE embedding MATCH :vector AND k = :k"
        ") "
        "SELECT c.id, knn.distance FROM knn "
        "JOIN chunks c ON c.id = knn.rowid "
        "JOIN documents d ON d.id = c.document_id "
        "WHERE d.workspace_id = :ws "
    )
    params: dict[str, object] = {
        "vector": vector,
        "k": CANDIDATES,
        "ws": workspace_id,
    }
    if document_ids is not None:
        sql += "AND c.document_id IN :document_ids"
        params["document_ids"] = list(document_ids)
    statement = text(sql)
    if document_ids is not None:
        statement = statement.bindparams(bindparam("document_ids", expanding=True))
    rows = session.execute(statement, params)
    # Cosine similarity, and a passage pointing the other way is no evidence at
    # all rather than evidence against, so it floors at nothing.
    return [(row.id, max(0.0, 1.0 - row.distance)) for row in rows]


def _best(
    session: Session, fused: dict[int, float], vector: bytes, top_k: int
) -> list[Hit]:
    """The best `top_k` blended candidates, closest breaking any tie.

    `score` stays the cosine similarity so a caller can still read how close a
    passage is, even though it no longer decides where the passage sits.
    """
    stmt = text(
        f"SELECT {_COLUMNS}, "
        "vec_distance_cosine(v.embedding, :vector) AS distance "
        "FROM chunks c JOIN chunk_vectors v ON v.rowid = c.id "
        "JOIN documents d ON d.id = c.document_id "
        "WHERE c.id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    rows = session.execute(stmt, {"vector": vector, "ids": list(fused)}).all()
    ordered = sorted(rows, key=lambda row: (-fused[row.id], row.distance))
    return [
        Hit(
            chunk_id=row.id,
            document_id=row.document_id,
            content=row.content,
            start_line=row.start_line,
            end_line=row.end_line,
            score=1.0 - row.distance,
            title=row.title,
        )
        for row in ordered[:top_k]
    ]
