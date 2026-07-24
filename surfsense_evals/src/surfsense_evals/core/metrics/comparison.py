"""Paired comparison statistics for head-to-head benchmarks.

In every head-to-head benchmark (currently MedXpertQA-MM and
MMLongBench-Doc) each question is answered by both arms (Native PDF
and SurfSense). That makes per-question outcomes paired, so
``McNemar's test`` on the discordant pairs is the right significance
test for "are the two arms different?". We also expose a bootstrap
delta CI for visualising effect size.

Aggregate cost / latency / token deltas are mean-based; the runner
slices them by arm before passing them in.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class McnemarResult:
    """Discordant pair counts + the test statistics."""

    n_total: int
    b: int  # native correct, surfsense wrong
    c: int  # native wrong,   surfsense correct
    statistic: float
    p_value: float
    method: str

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "n_total": self.n_total,
            "b_native_correct_only": self.b,
            "c_surfsense_correct_only": self.c,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "method": self.method,
        }


def mcnemar_test(
    arm_a_correct: Sequence[bool],
    arm_b_correct: Sequence[bool],
    *,
    use_exact_below: int = 11,
) -> McnemarResult:
    """Paired McNemar's test on per-question correctness.

    ``arm_a_correct`` is treated as the reference arm (typically the
    "native" arm); ``arm_b_correct`` is the challenger (typically
    "surfsense"). The test statistic only depends on discordant pairs.

    Default switch-over (``b + c < 11``): for very small discordant
    samples the exact binomial test is preferred; above that the
    continuity-corrected chi-square is well-behaved (Edwards 1948).
    Callers can raise ``use_exact_below`` if they prefer the more
    conservative ``b + c < 25`` rule.

    No external statistical package is required: scipy is a heavy dep
    and we only need binomial CDFs / chi-square sf, both implementable
    in stdlib + numpy without surprises.
    """

    if len(arm_a_correct) != len(arm_b_correct):
        raise ValueError(f"Length mismatch: arm_a={len(arm_a_correct)}, arm_b={len(arm_b_correct)}")
    n = len(arm_a_correct)
    b = sum(1 for a, c in zip(arm_a_correct, arm_b_correct, strict=False) if a and not c)
    c = sum(1 for a, cc in zip(arm_a_correct, arm_b_correct, strict=False) if (not a) and cc)
    discordant = b + c
    if discordant == 0:
        return McnemarResult(n_total=n, b=b, c=c, statistic=0.0, p_value=1.0, method="degenerate")

    if discordant < use_exact_below:
        # Exact binomial: under H0 each discordant pair is a Bernoulli(0.5).
        # p-value = 2 * P(X <= min(b,c) | n=discordant, p=0.5), capped at 1.
        k = min(b, c)
        cdf = sum(_binom_pmf(discordant, i) for i in range(k + 1))
        p_value = min(1.0, 2.0 * cdf)
        return McnemarResult(
            n_total=n, b=b, c=c, statistic=float(k), p_value=p_value, method="exact"
        )

    # Chi-square with continuity correction (McNemar-Edwards).
    chi = ((abs(b - c) - 1) ** 2) / discordant
    p_value = _chi2_sf(chi, df=1)
    return McnemarResult(n_total=n, b=b, c=c, statistic=chi, p_value=p_value, method="chi2_cc")


def _binom_pmf(n: int, k: int) -> float:
    return math.comb(n, k) * (0.5**n)


def _chi2_sf(x: float, *, df: int) -> float:
    """Survival function (1 - CDF) of chi-square; df=1 closed form."""

    if x <= 0:
        return 1.0
    if df == 1:
        # Chi^2(1) = N(0,1)^2; sf(x) = 2 * Phi_complement(sqrt(x))
        return math.erfc(math.sqrt(x / 2.0))
    # General fallback via regularized upper incomplete gamma.
    a = df / 2.0
    z = x / 2.0
    return _gammaincc(a, z)


def _gammaincc(a: float, x: float, *, max_iter: int = 200, tol: float = 1e-12) -> float:
    """Regularised upper incomplete gamma Q(a, x). Series + continued fraction."""

    if x < 0 or a <= 0:
        return float("nan")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        # Series for P(a, x); subtract from 1.
        p_series = _gammainc_series(a, x, max_iter=max_iter, tol=tol)
        return 1.0 - p_series
    return _gammaincc_cf(a, x, max_iter=max_iter, tol=tol)


def _gammainc_series(a: float, x: float, *, max_iter: int, tol: float) -> float:
    term = 1.0 / a
    summation = term
    for n in range(1, max_iter):
        term *= x / (a + n)
        summation += term
        if abs(term) < abs(summation) * tol:
            break
    log_pre = -x + a * math.log(x) - math.lgamma(a)
    return summation * math.exp(log_pre)


def _gammaincc_cf(a: float, x: float, *, max_iter: int, tol: float) -> float:
    b = x + 1.0 - a
    c_val = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, max_iter):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c_val = b + an / c_val
        if abs(c_val) < 1e-300:
            c_val = 1e-300
        d = 1.0 / d
        delta = d * c_val
        h *= delta
        if abs(delta - 1.0) < tol:
            break
    log_pre = -x + a * math.log(x) - math.lgamma(a)
    return h * math.exp(log_pre)


# ---------------------------------------------------------------------------
# Bootstrap delta CI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapDelta:
    delta: float
    ci_low: float
    ci_high: float
    n_resamples: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "delta": self.delta,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "n_resamples": self.n_resamples,
        }


def bootstrap_delta_ci(
    arm_a_correct: Sequence[bool],
    arm_b_correct: Sequence[bool],
    *,
    n_resamples: int = 5000,
    level: float = 0.95,
    random_state: int | None = 0,
) -> BootstrapDelta:
    """Paired-sample bootstrap CI for ``mean(arm_b) - mean(arm_a)``.

    Resamples *paired indices* with replacement so the dependency
    between arms is preserved.
    """

    if len(arm_a_correct) != len(arm_b_correct):
        raise ValueError("paired arms must have the same length")
    n = len(arm_a_correct)
    if n == 0:
        return BootstrapDelta(0.0, 0.0, 0.0, 0)
    a = np.asarray(arm_a_correct, dtype=np.int8)
    b = np.asarray(arm_b_correct, dtype=np.int8)
    delta = float(b.mean() - a.mean())

    rng = np.random.default_rng(random_state)
    deltas = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        deltas[i] = b[idx].mean() - a[idx].mean()
    alpha = (1.0 - level) / 2.0
    ci_low, ci_high = float(np.quantile(deltas, alpha)), float(np.quantile(deltas, 1 - alpha))
    return BootstrapDelta(delta=delta, ci_low=ci_low, ci_high=ci_high, n_resamples=n_resamples)


# ---------------------------------------------------------------------------
# Simple aggregate helpers (cost / latency / tokens)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Aggregate:
    mean: float
    median: float
    p95: float
    n: int

    def to_dict(self) -> dict[str, float | int]:
        return {"mean": self.mean, "median": self.median, "p95": self.p95, "n": self.n}


def paired_aggregate(values: Sequence[float]) -> Aggregate:
    """Mean / median / p95 of a list of numbers (e.g. cost-per-question)."""

    if not values:
        return Aggregate(0.0, 0.0, 0.0, 0)
    arr = np.asarray(values, dtype=np.float64)
    return Aggregate(
        mean=float(arr.mean()),
        median=float(statistics.median(values)),
        p95=float(np.quantile(arr, 0.95)),
        n=len(values),
    )


__all__ = [
    "Aggregate",
    "BootstrapDelta",
    "McnemarResult",
    "bootstrap_delta_ci",
    "mcnemar_test",
    "paired_aggregate",
]
