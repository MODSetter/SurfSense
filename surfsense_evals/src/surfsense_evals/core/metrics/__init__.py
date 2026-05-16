"""Pure-function metric primitives. Lazy imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .comparison import McnemarResult, bootstrap_delta_ci, mcnemar_test, paired_aggregate
    from .mc_accuracy import AccuracyResult, accuracy_with_wilson_ci, wilson_ci
    from .retrieval import RetrievalScores, mrr, ndcg_at_k, recall_at_k, score_run

__all__ = [
    "AccuracyResult",
    "McnemarResult",
    "RetrievalScores",
    "accuracy_with_wilson_ci",
    "bootstrap_delta_ci",
    "mcnemar_test",
    "mrr",
    "ndcg_at_k",
    "paired_aggregate",
    "recall_at_k",
    "score_run",
    "wilson_ci",
]


_MODULE_FOR = {
    "AccuracyResult": "mc_accuracy",
    "accuracy_with_wilson_ci": "mc_accuracy",
    "wilson_ci": "mc_accuracy",
    "RetrievalScores": "retrieval",
    "mrr": "retrieval",
    "ndcg_at_k": "retrieval",
    "recall_at_k": "retrieval",
    "score_run": "retrieval",
    "McnemarResult": "comparison",
    "bootstrap_delta_ci": "comparison",
    "mcnemar_test": "comparison",
    "paired_aggregate": "comparison",
}


def __getattr__(name: str):
    if name in _MODULE_FOR:
        from importlib import import_module

        mod = import_module(f".{_MODULE_FOR[name]}", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module 'surfsense_evals.core.metrics' has no attribute {name!r}")
