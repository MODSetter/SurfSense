"""Metric correctness — Wilson, McNemar, retrieval scores."""

from __future__ import annotations

import math

import pytest

from surfsense_evals.core.metrics import (
    accuracy_with_wilson_ci,
    bootstrap_delta_ci,
    mcnemar_test,
    mrr,
    ndcg_at_k,
    recall_at_k,
    score_run,
    wilson_ci,
)

# ---------------------------------------------------------------------------
# Wilson
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "k,n,low,high",
    [
        (80, 100, 0.7111, 0.8666),  # cross-checked vs statsmodels.proportion_confint(method='wilson')
        (50, 100, 0.4038, 0.5962),
        (0, 0, 0.0, 1.0),
        (0, 10, 0.0, 0.2775),
        (10, 10, 0.7225, 1.0),
    ],
)
def test_wilson_ci_known_values(k, n, low, high):
    result_low, result_high = wilson_ci(k, n)
    assert math.isclose(result_low, low, abs_tol=5e-4), (k, n, result_low, low)
    assert math.isclose(result_high, high, abs_tol=5e-4), (k, n, result_high, high)


def test_accuracy_with_wilson_ci_object():
    res = accuracy_with_wilson_ci(70, 100)
    assert res.accuracy == 0.7
    assert 0.0 < res.ci_low < res.ci_high < 1.0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        accuracy_with_wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        accuracy_with_wilson_ci(11, 10)


# ---------------------------------------------------------------------------
# McNemar
# ---------------------------------------------------------------------------


def test_mcnemar_degenerate_returns_p_value_one():
    a = [True, True, False, False]
    b = [True, True, False, False]
    res = mcnemar_test(a, b)
    assert res.b == 0 and res.c == 0
    assert res.p_value == 1.0
    assert res.method == "degenerate"


def test_mcnemar_exact_branch_strong_signal():
    """B = 0, C = 10 → exact two-sided binomial p == 2 * (1/2)**10."""

    a = [True] * 10 + [False] * 10
    b = [True] * 10 + [True] * 10  # surfsense beats native on the 10 native-wrong
    res = mcnemar_test(a, b)
    assert res.b == 0
    assert res.c == 10
    assert res.method == "exact"
    expected = 2 * (0.5 ** 10)
    assert math.isclose(res.p_value, expected, rel_tol=1e-9)


def test_mcnemar_chi_square_approx_for_large_discordant():
    # Construct b=15, c=5 with continuity-corrected chi^2 = (|10|-1)^2/20 = 4.05.
    a = [True] * 15 + [False] * 5 + [True] * 30 + [False] * 30
    b = [False] * 15 + [True] * 5 + [True] * 30 + [False] * 30
    res = mcnemar_test(a, b)
    assert res.method == "chi2_cc"
    assert res.b == 15 and res.c == 5
    assert math.isclose(res.statistic, ((abs(15 - 5) - 1) ** 2) / 20.0, rel_tol=1e-9)
    # p ≈ chi2.sf(4.05, df=1) ≈ 0.04417
    assert 0.04 < res.p_value < 0.05


def test_mcnemar_length_mismatch():
    with pytest.raises(ValueError):
        mcnemar_test([True], [True, False])


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_delta_ci_shape_and_determinism():
    a = [True, True, False, True, False, False, True, True]
    b = [True, True, True, True, True, False, True, False]
    res1 = bootstrap_delta_ci(a, b, n_resamples=500, random_state=42)
    res2 = bootstrap_delta_ci(a, b, n_resamples=500, random_state=42)
    assert res1.delta == res2.delta
    assert res1.ci_low == res2.ci_low
    assert res1.ci_high == res2.ci_high
    assert res1.ci_low <= res1.delta <= res1.ci_high
    assert res1.n_resamples == 500


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def test_recall_at_k():
    retrieved = ["a", "b", "c", "d"]
    relevant = ["b", "d", "z"]
    assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 3)
    assert recall_at_k(retrieved, relevant, k=4) == pytest.approx(2 / 3)


def test_mrr():
    assert mrr(["a", "b", "c"], ["c"]) == pytest.approx(1 / 3)
    assert mrr(["x", "y"], ["z"]) == 0.0


def test_ndcg_at_k_perfect_order():
    qrels = {"a": 2, "b": 1}
    assert ndcg_at_k(["a", "b"], qrels, k=2) == pytest.approx(1.0)


def test_ndcg_at_k_irrelevant_first():
    qrels = {"a": 2, "b": 1}
    # Wrong order should still be > 0 but < 1
    val = ndcg_at_k(["c", "a", "b"], qrels, k=3)
    assert 0 < val < 1


def test_score_run_aggregates_across_queries():
    scores = score_run(
        per_query_retrieved={"q1": ["a", "b"], "q2": ["x", "y", "z"]},
        per_query_qrels={"q1": {"a": 1}, "q2": {"z": 2}},
        ks=(1, 5),
        ndcg_k=5,
    )
    assert scores.n_queries == 2
    assert scores.recall_at_k[1] == pytest.approx((1 + 0) / 2)  # q1 hits @1, q2 doesn't
    assert scores.mrr == pytest.approx((1.0 + 1 / 3) / 2)
