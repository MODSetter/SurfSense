"""Retrieval metrics: Recall@k, MRR, nDCG@k.

Used by CUREv1's runner to score the SurfSense arm against the
benchmark's qrels. ``corpus_id`` is the canonical CUREv1 passage id
(string); the runner maps SurfSense ``chunk_id`` → ``document_id`` →
``corpus_id`` before calling these.

Graded relevance (CUREv1 uses 0/1/2 grades) is honoured by ``ndcg_at_k``;
``recall_at_k`` and ``mrr`` flatten anything > 0 to "relevant".
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalScores:
    """Aggregated retrieval scores."""

    recall_at_k: dict[int, float]
    mrr: float
    ndcg_at_10: float
    n_queries: int

    def to_dict(self) -> dict:
        return {
            "recall_at_k": dict(self.recall_at_k),
            "mrr": self.mrr,
            "ndcg_at_10": self.ndcg_at_10,
            "n_queries": self.n_queries,
        }


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of ``relevant`` documents found in ``retrieved[:k]``."""

    if not relevant:
        return 0.0
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    top_k = list(retrieved)[:k]
    hits = sum(1 for doc in top_k if doc in relevant_set)
    return hits / len(relevant_set)


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Reciprocal rank of the first relevant doc, 0 if none found."""

    relevant_set = set(relevant)
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant_set:
            return 1.0 / rank
    return 0.0


def _dcg_at_k(grades: Sequence[float], k: int) -> float:
    s = 0.0
    for i, grade in enumerate(grades[:k], start=1):
        # Standard log-base-2 discount; gain = 2^grade - 1 for graded relevance.
        s += (2.0 ** grade - 1.0) / math.log2(i + 1)
    return s


def ndcg_at_k(
    retrieved: Sequence[str],
    qrels: Mapping[str, float],
    k: int,
) -> float:
    """nDCG@k against graded ``qrels`` (``{doc_id: grade}``).

    Unjudged documents in ``retrieved`` contribute zero gain. The
    ideal ordering is ``qrels`` sorted by grade descending.
    """

    if not qrels:
        return 0.0
    grades = [float(qrels.get(doc, 0.0)) for doc in retrieved]
    dcg = _dcg_at_k(grades, k)
    ideal = sorted(qrels.values(), reverse=True)
    idcg = _dcg_at_k([float(g) for g in ideal], k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def score_run(
    *,
    per_query_retrieved: Mapping[str, Sequence[str]],
    per_query_qrels: Mapping[str, Mapping[str, float]],
    ks: Sequence[int] = (1, 5, 10, 32),
    ndcg_k: int = 10,
) -> RetrievalScores:
    """Aggregate Recall@k, MRR, nDCG@k across a run.

    ``per_query_retrieved`` maps ``query_id -> ordered list of doc ids``.
    ``per_query_qrels`` maps ``query_id -> {doc_id: grade}`` (grade > 0
    is relevant).

    Queries present in retrieved but not in qrels are skipped. Queries
    in qrels but missing from retrieved contribute zeros.
    """

    qids = set(per_query_qrels.keys()) & set(per_query_retrieved.keys())
    if not qids:
        return RetrievalScores(recall_at_k={k: 0.0 for k in ks}, mrr=0.0, ndcg_at_10=0.0, n_queries=0)

    recall_totals = {k: 0.0 for k in ks}
    mrr_total = 0.0
    ndcg_total = 0.0
    for qid in qids:
        retrieved = list(per_query_retrieved[qid])
        qrels = per_query_qrels[qid]
        relevant_docs = [d for d, g in qrels.items() if g > 0]
        for k in ks:
            recall_totals[k] += recall_at_k(retrieved, relevant_docs, k)
        mrr_total += mrr(retrieved, relevant_docs)
        ndcg_total += ndcg_at_k(retrieved, qrels, ndcg_k)

    n = len(qids)
    return RetrievalScores(
        recall_at_k={k: v / n for k, v in recall_totals.items()},
        mrr=mrr_total / n,
        ndcg_at_10=ndcg_total / n,
        n_queries=n,
    )


__all__ = ["RetrievalScores", "mrr", "ndcg_at_k", "recall_at_k", "score_run"]
