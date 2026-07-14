"""Multiple-choice accuracy + Wilson 95% confidence intervals.

Wilson CI is preferred over normal-approximation because MIRAGE's
per-task subsets can be small (PubMedQA* and BioASQ-Y/N have a few
hundred questions each) and Wilson handles n→0 / p→{0,1} edges
gracefully.

Reference for the closed form: Wilson (1927); identical to the
``statsmodels.stats.proportion.proportion_confint(method='wilson')``
output and what scikit-learn implements internally for its bounded
estimators.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AccuracyResult:
    """Per-task accuracy with Wilson CI."""

    n_correct: int
    n_total: int
    accuracy: float
    ci_low: float
    ci_high: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "n_correct": self.n_correct,
            "n_total": self.n_total,
            "accuracy": self.accuracy,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
        }


# Two-sided Wilson z values. 1.959964 ≈ z_{0.975}.
_Z_FOR_LEVEL: dict[float, float] = {
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}


def wilson_ci(n_correct: int, n_total: int, *, level: float = 0.95) -> tuple[float, float]:
    """Two-sided Wilson score confidence interval for a proportion.

    Returns ``(low, high)``. ``n_total == 0`` returns ``(0.0, 1.0)`` —
    the maximally uncertain interval.
    """

    if n_total <= 0:
        return 0.0, 1.0
    if level not in _Z_FOR_LEVEL:
        raise ValueError(f"Unsupported confidence level {level!r}")
    z = _Z_FOR_LEVEL[level]
    p = n_correct / n_total
    n = n_total
    denom = 1.0 + (z * z) / n
    centre = (p + (z * z) / (2 * n)) / denom
    half = (z / denom) * math.sqrt((p * (1 - p) / n) + (z * z) / (4 * n * n))
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return low, high


def accuracy_with_wilson_ci(n_correct: int, n_total: int, *, level: float = 0.95) -> AccuracyResult:
    if n_total < 0:
        raise ValueError(f"n_total must be >= 0, got {n_total}")
    if n_correct < 0 or n_correct > n_total:
        raise ValueError(
            f"n_correct must be in [0, n_total]; got n_correct={n_correct}, n_total={n_total}"
        )
    accuracy = (n_correct / n_total) if n_total > 0 else 0.0
    low, high = wilson_ci(n_correct, n_total, level=level)
    return AccuracyResult(
        n_correct=n_correct,
        n_total=n_total,
        accuracy=accuracy,
        ci_low=low,
        ci_high=high,
    )


def per_task_accuracy(
    rows: Sequence[Mapping[str, object]],
    *,
    task_key: str = "task",
    correct_key: str = "is_correct",
    level: float = 0.95,
) -> dict[str, AccuracyResult]:
    """Group ``rows`` by ``task_key`` and compute per-task ``AccuracyResult``.

    ``rows[i][correct_key]`` must be truthy iff the answer was correct.
    """

    counts: dict[str, list[int]] = {}
    for row in rows:
        task = str(row.get(task_key, ""))
        bucket = counts.setdefault(task, [0, 0])
        bucket[1] += 1
        if row.get(correct_key):
            bucket[0] += 1
    return {task: accuracy_with_wilson_ci(c[0], c[1], level=level) for task, c in counts.items()}


def macro_accuracy(per_task: Mapping[str, AccuracyResult]) -> float:
    if not per_task:
        return 0.0
    return sum(r.accuracy for r in per_task.values()) / len(per_task)


__all__ = [
    "AccuracyResult",
    "accuracy_with_wilson_ci",
    "macro_accuracy",
    "per_task_accuracy",
    "wilson_ci",
]
