"""Unit tests for the Auto (Fastest) quality scoring module."""

from __future__ import annotations

import time

import pytest

from app.services.quality_score import (
    _HEALTH_GATE_UPTIME_PCT,
    _OPERATOR_TRUST_BONUS,
    aggregate_health,
    capabilities_signal,
    context_signal,
    created_recency_signal,
    pricing_band,
    slug_penalty,
    static_score_or,
    static_score_yaml,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# created_recency_signal
# ---------------------------------------------------------------------------


def test_created_recency_signal_recent_model_scores_high():
    now = 1_750_000_000  # ~mid-2025
    one_month_ago = now - (30 * 86_400)
    assert created_recency_signal(one_month_ago, now) == 20


def test_created_recency_signal_old_model_scores_zero():
    now = 1_750_000_000
    five_years_ago = now - (5 * 365 * 86_400)
    assert created_recency_signal(five_years_ago, now) == 0


def test_created_recency_signal_missing_timestamp_is_neutral():
    now = 1_750_000_000
    assert created_recency_signal(None, now) == 0
    assert created_recency_signal(0, now) == 0


def test_created_recency_signal_monotonic_decay():
    now = 1_750_000_000
    scores = [
        created_recency_signal(now - days * 86_400, now)
        for days in (30, 120, 300, 500, 700, 1000, 1500)
    ]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# pricing_band
# ---------------------------------------------------------------------------


def test_pricing_band_free_returns_zero():
    assert pricing_band("0", "0") == 0
    assert pricing_band(0.0, 0.0) == 0
    assert pricing_band(None, None) == 0


def test_pricing_band_handles_unparseable():
    assert pricing_band("not-a-number", "0") == 0
    assert pricing_band({}, []) == 0  # type: ignore[arg-type]


def test_pricing_band_premium_tiers_increase_with_price():
    cheap = pricing_band("0.0000003", "0.0000005")
    mid = pricing_band("0.000003", "0.000015")
    flagship = pricing_band("0.00001", "0.00005")
    assert 0 < cheap < mid < flagship


# ---------------------------------------------------------------------------
# context_signal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ctx,expected",
    [
        (1_500_000, 10),
        (1_000_000, 10),
        (500_000, 8),
        (200_000, 6),
        (128_000, 4),
        (100_000, 2),
        (50_000, 0),
        (0, 0),
        (None, 0),
    ],
)
def test_context_signal_bands(ctx, expected):
    assert context_signal(ctx) == expected


# ---------------------------------------------------------------------------
# capabilities_signal
# ---------------------------------------------------------------------------


def test_capabilities_signal_caps_at_five():
    assert capabilities_signal(
        ["tools", "structured_outputs", "reasoning", "include_reasoning"]
    ) <= 5


def test_capabilities_signal_tools_only():
    assert capabilities_signal(["tools"]) == 2


def test_capabilities_signal_empty():
    assert capabilities_signal(None) == 0
    assert capabilities_signal([]) == 0


# ---------------------------------------------------------------------------
# slug_penalty
# ---------------------------------------------------------------------------


def test_slug_penalty_demotes_tiny_models():
    assert slug_penalty("meta-llama/llama-3.2-1b-instruct") < 0
    assert slug_penalty("liquid/lfm-7b") < 0
    assert slug_penalty("google/gemma-3n-e4b-it") < 0


def test_slug_penalty_skips_capable_mini_nano_lite_models():
    """Critical Option C+ regression: don't penalise modern frontier
    models named ``-nano`` / ``-mini`` / ``-lite`` (gpt-5-mini, etc.)."""
    assert slug_penalty("openai/gpt-5-mini") == 0
    assert slug_penalty("openai/gpt-5-nano") == 0
    assert slug_penalty("google/gemini-2.5-flash-lite") == 0
    assert slug_penalty("anthropic/claude-haiku-4.5") == 0


def test_slug_penalty_demotes_legacy_variants():
    assert slug_penalty("openai/o1-preview") < 0
    assert slug_penalty("foo/bar-base") < 0
    assert slug_penalty("foo/bar-distill") < 0


def test_slug_penalty_empty_input():
    assert slug_penalty("") == 0


# ---------------------------------------------------------------------------
# static_score_or
# ---------------------------------------------------------------------------


def _or_model(
    *,
    model_id: str,
    created: int | None = None,
    prompt: str = "0.000003",
    completion: str = "0.000015",
    context: int = 200_000,
    params: list[str] | None = None,
) -> dict:
    return {
        "id": model_id,
        "created": created,
        "pricing": {"prompt": prompt, "completion": completion},
        "context_length": context,
        "supported_parameters": params if params is not None else ["tools"],
    }


def test_static_score_or_frontier_premium_beats_free_tiny():
    now = 1_750_000_000
    frontier = _or_model(
        model_id="openai/gpt-5",
        created=now - (60 * 86_400),
        prompt="0.000005",
        completion="0.000020",
        context=400_000,
        params=["tools", "structured_outputs", "reasoning"],
    )
    tiny_free = _or_model(
        model_id="meta-llama/llama-3.2-1b-instruct:free",
        created=now - (5 * 365 * 86_400),
        prompt="0",
        completion="0",
        context=128_000,
        params=["tools"],
    )
    assert static_score_or(frontier, now_ts=now) > static_score_or(
        tiny_free, now_ts=now
    )


def test_static_score_or_score_is_clamped_0_to_100():
    now = int(time.time())
    score = static_score_or(_or_model(model_id="openai/gpt-4o"), now_ts=now)
    assert 0 <= score <= 100


def test_static_score_or_unknown_provider_is_neutral_not_zero():
    now = int(time.time())
    score = static_score_or(
        _or_model(model_id="some-new-lab/some-model"),
        now_ts=now,
    )
    assert score > 0


def test_static_score_or_recent_release_beats_year_old_same_provider():
    now = 1_750_000_000
    fresh = _or_model(model_id="openai/gpt-5", created=now - (60 * 86_400))
    old = _or_model(model_id="openai/gpt-4-turbo", created=now - (700 * 86_400))
    assert static_score_or(fresh, now_ts=now) > static_score_or(old, now_ts=now)


# ---------------------------------------------------------------------------
# static_score_yaml
# ---------------------------------------------------------------------------


def test_static_score_yaml_includes_operator_bonus():
    cfg = {
        "provider": "AZURE_OPENAI",
        "model_name": "gpt-5",
        "litellm_params": {"base_model": "azure/gpt-5"},
    }
    score = static_score_yaml(cfg)
    assert score >= _OPERATOR_TRUST_BONUS


def test_static_score_yaml_unknown_provider_still_carries_bonus():
    cfg = {
        "provider": "SOME_NEW_PROVIDER",
        "model_name": "weird-model",
    }
    score = static_score_yaml(cfg)
    assert score >= _OPERATOR_TRUST_BONUS


def test_static_score_yaml_clamped_0_to_100():
    cfg = {
        "provider": "AZURE_OPENAI",
        "model_name": "gpt-5",
        "litellm_params": {"base_model": "azure/gpt-5"},
    }
    assert 0 <= static_score_yaml(cfg) <= 100


# ---------------------------------------------------------------------------
# aggregate_health
# ---------------------------------------------------------------------------


def test_aggregate_health_gates_when_uptime_below_threshold():
    """Live data showed Venice-routed cfgs at 53-68%; this guards that the
    90% gate excludes them."""
    venice_endpoints = [
        {
            "status": 0,
            "uptime_last_30m": 0.55,
            "uptime_last_1d": 0.60,
            "uptime_last_5m": 0.50,
        },
        {
            "status": 0,
            "uptime_last_30m": 0.65,
            "uptime_last_1d": 0.68,
            "uptime_last_5m": 0.62,
        },
    ]
    gated, score = aggregate_health(venice_endpoints)
    assert gated is True
    assert score is None


def test_aggregate_health_passes_for_healthy_provider():
    healthy = [
        {
            "status": 0,
            "uptime_last_30m": 0.99,
            "uptime_last_1d": 0.995,
            "uptime_last_5m": 0.99,
        },
    ]
    gated, score = aggregate_health(healthy)
    assert gated is False
    assert score is not None
    assert score >= _HEALTH_GATE_UPTIME_PCT


def test_aggregate_health_picks_best_endpoint_across_multiple():
    """Multi-endpoint aggregation should reward the best non-null uptime."""
    mixed = [
        {"status": 0, "uptime_last_30m": 0.55},
        {"status": 0, "uptime_last_30m": 0.97},  # this one passes the gate
    ]
    gated, score = aggregate_health(mixed)
    assert gated is False
    assert score is not None


def test_aggregate_health_empty_endpoints_gated():
    gated, score = aggregate_health([])
    assert gated is True
    assert score is None


def test_aggregate_health_no_status_zero_gated():
    """Even with high uptime, no OK status means the cfg is broken upstream."""
    endpoints = [
        {"status": 1, "uptime_last_30m": 0.99},
        {"status": 2, "uptime_last_30m": 0.98},
    ]
    gated, score = aggregate_health(endpoints)
    assert gated is True
    assert score is None


def test_aggregate_health_all_uptime_null_gated():
    endpoints = [
        {"status": 0, "uptime_last_30m": None, "uptime_last_1d": None},
    ]
    gated, score = aggregate_health(endpoints)
    assert gated is True
    assert score is None


def test_aggregate_health_pct_normalisation():
    """OpenRouter returns 0-1 fractions; some endpoints surface 0-100%
    percentages. Both should reach the same gate decision."""
    fraction_form = [{"status": 0, "uptime_last_30m": 0.95}]
    pct_form = [{"status": 0, "uptime_last_30m": 95.0}]
    g1, s1 = aggregate_health(fraction_form)
    g2, s2 = aggregate_health(pct_form)
    assert g1 == g2 == False  # noqa: E712
    assert s1 is not None and s2 is not None
    assert abs(s1 - s2) < 0.5
