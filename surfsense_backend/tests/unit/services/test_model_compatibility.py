"""Golden cases for the compatibility sweep's verdict.

The sweep decides which models users are allowed to reach, so it needs its own
tests before it is trusted to blocklist anything: wrongly marking a working
model dead is worse than not sweeping at all.

The error bodies below are verbatim from live OpenRouter responses captured by
``scripts/probe_openrouter_dead_models.py``.
"""

from __future__ import annotations

import pytest

from app.services.model_compatibility import (
    CompatibilityStatus,
    ProbeStage,
    classify_probe_failure,
    verdict_from_stages,
)

pytestmark = pytest.mark.unit


class _ProviderError(Exception):
    """Stands in for the litellm exception, which carries the body in str()."""


BATCH_404 = _ProviderError(
    '{"error":{"message":"This model is only available through the Batch API. '
    'Use the /api/beta/batches endpoint instead.","code":404}}'
)
DELISTED_404 = _ProviderError(
    '{"error":{"message":"No endpoints found for poolside/laguna-m.1.","code":404}}'
)
RATE_LIMITED = _ProviderError('{"error":{"message":"Rate limit exceeded","code":429}}')
UPSTREAM_502 = _ProviderError('{"error":{"message":"Bad gateway","code":502}}')
BAD_KEY_401 = _ProviderError(
    '{"error":{"message":"No auth credentials found","code":401}}'
)


def test_batch_variant_is_blocked():
    status, code = classify_probe_failure(BATCH_404)

    assert status is CompatibilityStatus.BLOCKED
    assert code == "model_not_found"


def test_delisted_model_is_blocked():
    status, _ = classify_probe_failure(DELISTED_404)

    assert status is CompatibilityStatus.BLOCKED


@pytest.mark.parametrize("exc", [RATE_LIMITED, UPSTREAM_502])
def test_transient_failures_never_blocklist(exc):
    """A busy or briefly broken provider must not cost a model its listing."""
    status, _ = classify_probe_failure(exc)

    assert status is CompatibilityStatus.UNKNOWN


def test_auth_failure_never_blocklists():
    """A bad key fails every model at once; blocklisting on it empties the
    catalogue in one sweep."""
    status, _ = classify_probe_failure(BAD_KEY_401)

    assert status is CompatibilityStatus.UNKNOWN


def test_known_good_model_passes_every_stage():
    verdict = verdict_from_stages(dict.fromkeys(ProbeStage))

    assert verdict.status is CompatibilityStatus.OK
    assert verdict.failure_stage is None
    assert verdict.error_code is None


def test_verdict_reports_the_first_failing_stage():
    verdict = verdict_from_stages(
        {
            ProbeStage.STREAM: None,
            ProbeStage.TOOL_BIND: BATCH_404,
            ProbeStage.TOOL_RESULT: None,
        }
    )

    assert verdict.status is CompatibilityStatus.BLOCKED
    assert verdict.failure_stage is ProbeStage.TOOL_BIND
    assert "Batch API" in (verdict.error_excerpt or "")


def test_unknown_at_any_stage_does_not_become_ok():
    verdict = verdict_from_stages(
        {ProbeStage.STREAM: RATE_LIMITED, ProbeStage.TOOL_BIND: None}
    )

    assert verdict.status is CompatibilityStatus.UNKNOWN
    assert verdict.failure_stage is ProbeStage.STREAM
