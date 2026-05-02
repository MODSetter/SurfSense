"""Unit tests for the OpenRouter ``_enrich_health`` background task."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.openrouter_integration_service import (
    OpenRouterIntegrationService,
)
from app.services.quality_score import (
    _HEALTH_FAIL_RATIO_FALLBACK,
)

pytestmark = pytest.mark.unit


def _or_cfg(
    *,
    cid: int,
    model_name: str,
    tier: str = "premium",
    static_score: int = 50,
) -> dict:
    return {
        "id": cid,
        "provider": "OPENROUTER",
        "model_name": model_name,
        "billing_tier": tier,
        "auto_pin_tier": "B" if tier == "premium" else "C",
        "quality_score_static": static_score,
        "quality_score_health": None,
        "quality_score": static_score,
        "health_gated": False,
    }


class _StubResponse:
    def __init__(self, *, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _StubAsyncClient:
    """Minimal drop-in for ``httpx.AsyncClient`` used by ``_fetch_endpoints``."""

    def __init__(self, responder):
        self._responder = responder
        self.requests: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict | None = None) -> _StubResponse:
        self.requests.append(url)
        return self._responder(url)


def _patch_async_client(monkeypatch, responder) -> _StubAsyncClient:
    """Replace ``httpx.AsyncClient`` for the duration of the test."""
    client = _StubAsyncClient(responder)
    monkeypatch.setattr(
        "app.services.openrouter_integration_service.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    return client


def _healthy_payload() -> dict:
    return {
        "data": {
            "endpoints": [
                {
                    "status": 0,
                    "uptime_last_30m": 0.99,
                    "uptime_last_1d": 0.995,
                    "uptime_last_5m": 0.99,
                }
            ]
        }
    }


def _unhealthy_payload() -> dict:
    return {
        "data": {
            "endpoints": [
                {
                    "status": 0,
                    "uptime_last_30m": 0.55,
                    "uptime_last_1d": 0.62,
                    "uptime_last_5m": 0.50,
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Bounded fan-out + happy path
# ---------------------------------------------------------------------------


async def test_enrich_health_marks_healthy_and_gates_unhealthy(monkeypatch):
    cfgs = [
        _or_cfg(cid=-1, model_name="anthropic/claude-haiku", static_score=70),
        _or_cfg(cid=-2, model_name="venice/dead-model", static_score=60),
    ]

    def responder(url: str) -> _StubResponse:
        if "anthropic" in url:
            return _StubResponse(payload=_healthy_payload())
        return _StubResponse(payload=_unhealthy_payload())

    _patch_async_client(monkeypatch, responder)

    service = OpenRouterIntegrationService()
    service._settings = {"api_key": ""}
    await service._enrich_health(cfgs)

    healthy = next(c for c in cfgs if c["id"] == -1)
    gated = next(c for c in cfgs if c["id"] == -2)

    assert healthy["health_gated"] is False
    assert healthy["quality_score_health"] is not None
    assert healthy["quality_score"] >= healthy["quality_score_static"]

    assert gated["health_gated"] is True
    assert gated["quality_score"] == gated["quality_score_static"]


async def test_enrich_health_only_touches_or_provider(monkeypatch):
    """YAML cfgs that aren't OPENROUTER must be skipped entirely."""
    yaml_cfg = {
        "id": -1,
        "provider": "AZURE_OPENAI",
        "model_name": "gpt-5",
        "billing_tier": "premium",
        "auto_pin_tier": "A",
        "quality_score_static": 80,
        "quality_score": 80,
        "health_gated": False,
    }
    or_cfg = _or_cfg(cid=-2, model_name="anthropic/claude-haiku")

    requests: list[str] = []

    def responder(url: str) -> _StubResponse:
        requests.append(url)
        return _StubResponse(payload=_healthy_payload())

    _patch_async_client(monkeypatch, responder)

    service = OpenRouterIntegrationService()
    service._settings = {}
    await service._enrich_health([yaml_cfg, or_cfg])

    assert all("anthropic/claude-haiku" in r for r in requests)
    # YAML cfg is untouched.
    assert yaml_cfg["quality_score"] == 80
    assert yaml_cfg["health_gated"] is False


# ---------------------------------------------------------------------------
# Failure ratio fallback
# ---------------------------------------------------------------------------


async def test_enrich_health_falls_back_to_last_good_when_failure_ratio_high(
    monkeypatch,
):
    """If >= 25% of fetches fail, keep last-good cache instead of writing
    partial data."""
    cfgs = [
        _or_cfg(cid=-1, model_name="anthropic/claude-haiku", static_score=70),
        _or_cfg(cid=-2, model_name="openai/gpt-5", static_score=80),
        _or_cfg(cid=-3, model_name="google/gemini-flash", static_score=65),
        _or_cfg(cid=-4, model_name="venice/something", static_score=50),
    ]

    service = OpenRouterIntegrationService()
    service._settings = {}
    # Pre-seed last-good cache with a known-healthy snapshot.
    service._health_cache = {
        "anthropic/claude-haiku": {"gated": False, "score": 95.0},
    }

    def all_fail(_url: str) -> _StubResponse:
        return _StubResponse(payload={}, status_code=500)

    _patch_async_client(monkeypatch, all_fail)
    await service._enrich_health(cfgs)

    # Above threshold ⇒ degraded; last-good cache wins for the cached cfg.
    cached_hit = next(c for c in cfgs if c["model_name"] == "anthropic/claude-haiku")
    assert cached_hit["quality_score_health"] == 95.0
    assert cached_hit["health_gated"] is False
    # Confirm the threshold constant we're testing against is real.
    assert _HEALTH_FAIL_RATIO_FALLBACK <= 1.0


async def test_enrich_health_keeps_static_only_with_no_cache_and_failures(
    monkeypatch,
):
    """If a fetch fails and there's no last-good cache, the cfg keeps its
    static-only ``quality_score`` and is *not* gated by default."""
    cfgs = [
        _or_cfg(cid=-1, model_name="anthropic/claude-haiku", static_score=70),
    ]

    def fail(_url: str) -> _StubResponse:
        return _StubResponse(payload={}, status_code=500)

    _patch_async_client(monkeypatch, fail)

    service = OpenRouterIntegrationService()
    service._settings = {}
    await service._enrich_health(cfgs)

    cfg = cfgs[0]
    assert cfg["health_gated"] is False
    assert cfg["quality_score"] == cfg["quality_score_static"]
    assert cfg["quality_score_health"] is None


# ---------------------------------------------------------------------------
# Last-good cache: success populates, next failure reuses
# ---------------------------------------------------------------------------


async def test_enrich_health_populates_cache_on_success_then_reuses_on_failure(
    monkeypatch,
):
    cfg = _or_cfg(cid=-1, model_name="anthropic/claude-haiku", static_score=70)

    service = OpenRouterIntegrationService()
    service._settings = {}

    def healthy(_url: str) -> _StubResponse:
        return _StubResponse(payload=_healthy_payload())

    _patch_async_client(monkeypatch, healthy)
    await service._enrich_health([cfg])

    assert "anthropic/claude-haiku" in service._health_cache
    cached_score = service._health_cache["anthropic/claude-haiku"]["score"]
    assert cached_score is not None

    # Next cycle: enough other healthy cfgs so failure ratio stays below
    # the 25% threshold even when this one fails individually.
    other_cfgs = [
        _or_cfg(cid=-2 - i, model_name=f"healthy/m-{i}", static_score=60)
        for i in range(10)
    ]
    cfg["quality_score_health"] = None
    cfg["quality_score"] = cfg["quality_score_static"]

    def mixed(url: str) -> _StubResponse:
        if "anthropic" in url:
            return _StubResponse(payload={}, status_code=500)
        return _StubResponse(payload=_healthy_payload())

    _patch_async_client(monkeypatch, mixed)
    await service._enrich_health([cfg, *other_cfgs])

    assert cfg["quality_score_health"] == cached_score
    assert cfg["health_gated"] is False


# ---------------------------------------------------------------------------
# Bounded fan-out: respects top-N caps
# ---------------------------------------------------------------------------


async def test_enrich_health_bounds_premium_fanout(monkeypatch):
    """Top-N premium cap is honoured even when many cfgs are present."""
    from app.services.quality_score import _HEALTH_ENRICH_TOP_N_PREMIUM

    cfgs = [
        _or_cfg(
            cid=-i, model_name=f"openai/m-{i}", tier="premium", static_score=100 - i
        )
        for i in range(1, _HEALTH_ENRICH_TOP_N_PREMIUM + 20)
    ]

    seen: list[str] = []

    def responder(url: str) -> _StubResponse:
        seen.append(url)
        return _StubResponse(payload=_healthy_payload())

    _patch_async_client(monkeypatch, responder)

    service = OpenRouterIntegrationService()
    service._settings = {}
    await service._enrich_health(cfgs)

    assert len(seen) == _HEALTH_ENRICH_TOP_N_PREMIUM


async def test_enrich_health_no_or_cfgs_is_noop(monkeypatch):
    """When the catalogue has no OR cfgs at all, no HTTP calls fire."""
    yaml_cfg: dict[str, Any] = {
        "id": -1,
        "provider": "AZURE_OPENAI",
        "model_name": "gpt-5",
        "billing_tier": "premium",
    }
    requests: list[str] = []

    def responder(url: str) -> _StubResponse:
        requests.append(url)
        return _StubResponse(payload=_healthy_payload())

    _patch_async_client(monkeypatch, responder)

    service = OpenRouterIntegrationService()
    service._settings = {}
    await service._enrich_health([yaml_cfg])
    assert requests == []
