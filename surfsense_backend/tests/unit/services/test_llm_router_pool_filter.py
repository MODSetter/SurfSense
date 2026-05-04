"""LLMRouterService pool-filter / rebuild tests.

These tests focus on the *config plumbing* (which configs enter the router
pool, rebuild resets state correctly). They stub out the underlying
``litellm.Router`` so we don't need real API keys or network access.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.llm_router_service import LLMRouterService

pytestmark = pytest.mark.unit


def _fake_yaml_config(
    *,
    id: int,
    model_name: str,
    billing_tier: str = "free",
) -> dict:
    return {
        "id": id,
        "name": f"yaml-{id}",
        "provider": "OPENAI",
        "model_name": model_name,
        "api_key": "sk-test",
        "api_base": "",
        "billing_tier": billing_tier,
        "rpm": 100,
        "tpm": 100_000,
        "litellm_params": {},
    }


def _fake_openrouter_config(
    *,
    id: int,
    model_name: str,
    billing_tier: str,
    router_pool_eligible: bool | None = None,
) -> dict:
    """Build a synthetic dynamic-OR config dict for router-pool tests.

    Defaults mirror Strategy 3: premium OR enters the pool, free OR stays
    out. Callers can override ``router_pool_eligible`` to simulate legacy
    configs or to regression-test the filter mechanics directly.
    """
    if router_pool_eligible is None:
        router_pool_eligible = billing_tier == "premium"
    return {
        "id": id,
        "name": f"or-{id}",
        "provider": "OPENROUTER",
        "model_name": model_name,
        "api_key": "sk-or-test",
        "api_base": "",
        "billing_tier": billing_tier,
        "rpm": 20 if billing_tier == "free" else 200,
        "tpm": 100_000 if billing_tier == "free" else 1_000_000,
        "litellm_params": {},
        "router_pool_eligible": router_pool_eligible,
    }


def _reset_router_singleton() -> None:
    instance = LLMRouterService.get_instance()
    instance._initialized = False
    instance._router = None
    instance._model_list = []
    instance._premium_model_strings = set()


def test_router_pool_includes_or_premium_excludes_or_free():
    """Strategy 3: premium OR joins the pool, free OR stays out.

    Dynamic OpenRouter premium entries opt into load balancing alongside
    curated YAML configs. Dynamic OR free entries are intentionally kept
    out because OpenRouter's free tier enforces a single account-global
    quota bucket that per-deployment router accounting can't represent.
    """
    _reset_router_singleton()
    configs = [
        _fake_yaml_config(id=-1, model_name="gpt-4o", billing_tier="premium"),
        _fake_yaml_config(id=-2, model_name="gpt-4o-mini", billing_tier="free"),
        _fake_openrouter_config(
            id=-10_001, model_name="openai/gpt-4o", billing_tier="premium"
        ),
        _fake_openrouter_config(
            id=-10_002,
            model_name="meta-llama/llama-3.3-70b:free",
            billing_tier="free",
        ),
    ]

    with (
        patch("app.services.llm_router_service.Router") as mock_router,
        patch(
            "app.services.llm_router_service.LLMRouterService._build_context_fallback_groups"
        ) as mock_ctx_fb,
    ):
        mock_ctx_fb.side_effect = lambda ml: (ml, None)
        mock_router.return_value = object()
        LLMRouterService.initialize(configs)

    pool_models = {
        dep["litellm_params"]["model"]
        for dep in LLMRouterService.get_instance()._model_list
    }
    # YAML premium + YAML free + dynamic OR premium are all in the pool.
    # Dynamic OR free is NOT (shared-bucket rate limits can't be load-balanced).
    assert pool_models == {
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "openrouter/openai/gpt-4o",
    }

    prem = LLMRouterService.get_instance()._premium_model_strings
    # YAML premium is fingerprinted under both its model_string and its
    # ``base_model`` form (existing behavior we don't want to regress).
    assert "openai/gpt-4o" in prem
    # Dynamic OR premium is now fingerprinted as premium so pool-level
    # calls through the router are billed against premium quota.
    assert "openrouter/openai/gpt-4o" in prem
    assert LLMRouterService.is_premium_model("openrouter/openai/gpt-4o") is True
    # Dynamic OR free never enters the pool, so it's never counted as premium.
    assert (
        LLMRouterService.is_premium_model("openrouter/meta-llama/llama-3.3-70b:free")
        is False
    )


def test_router_pool_filter_mechanics_respect_override():
    """The ``router_pool_eligible`` filter itself works independently of tier.

    Regression guard: if a future refactor ever sets the flag False on a
    premium config (e.g. for maintenance), that config MUST be skipped by
    ``initialize`` even though its tier is premium.
    """
    _reset_router_singleton()
    configs = [
        _fake_yaml_config(id=-1, model_name="gpt-4o", billing_tier="premium"),
        _fake_openrouter_config(
            id=-10_001,
            model_name="openai/gpt-4o",
            billing_tier="premium",
            router_pool_eligible=False,  # opt out despite being premium
        ),
    ]

    with (
        patch("app.services.llm_router_service.Router") as mock_router,
        patch(
            "app.services.llm_router_service.LLMRouterService._build_context_fallback_groups"
        ) as mock_ctx_fb,
    ):
        mock_ctx_fb.side_effect = lambda ml: (ml, None)
        mock_router.return_value = object()
        LLMRouterService.initialize(configs)

    pool_models = {
        dep["litellm_params"]["model"]
        for dep in LLMRouterService.get_instance()._model_list
    }
    assert pool_models == {"openai/gpt-4o"}
    assert LLMRouterService.is_premium_model("openrouter/openai/gpt-4o") is False


def test_rebuild_refreshes_pool_after_configs_change():
    _reset_router_singleton()
    configs_v1 = [
        _fake_yaml_config(id=-1, model_name="gpt-4o", billing_tier="premium"),
    ]
    configs_v2 = [
        *configs_v1,
        _fake_yaml_config(id=-2, model_name="gpt-4o-mini", billing_tier="free"),
    ]

    with (
        patch("app.services.llm_router_service.Router") as mock_router,
        patch(
            "app.services.llm_router_service.LLMRouterService._build_context_fallback_groups"
        ) as mock_ctx_fb,
    ):
        mock_ctx_fb.side_effect = lambda ml: (ml, None)
        mock_router.return_value = object()

        LLMRouterService.initialize(configs_v1)
        assert len(LLMRouterService.get_instance()._model_list) == 1

        # ``initialize`` should be a no-op here (already initialized).
        LLMRouterService.initialize(configs_v2)
        assert len(LLMRouterService.get_instance()._model_list) == 1

        # ``rebuild`` must clear the guard and re-run with the new configs.
        LLMRouterService.rebuild(configs_v2)
        assert len(LLMRouterService.get_instance()._model_list) == 2


def test_auto_model_pin_candidates_include_dynamic_openrouter():
    """Dynamic OR configs must remain Auto-mode thread-pin candidates.

    Guards against a future regression where someone adds the
    ``router_pool_eligible`` filter to ``auto_model_pin_service._global_candidates``.
    """
    from app.config import config
    from app.services.auto_model_pin_service import _global_candidates

    or_premium = _fake_openrouter_config(
        id=-10_001, model_name="openai/gpt-4o", billing_tier="premium"
    )
    or_free = _fake_openrouter_config(
        id=-10_002,
        model_name="meta-llama/llama-3.3-70b:free",
        billing_tier="free",
    )
    original = config.GLOBAL_LLM_CONFIGS
    try:
        config.GLOBAL_LLM_CONFIGS = [or_premium, or_free]
        candidate_ids = {c["id"] for c in _global_candidates()}
        assert candidate_ids == {-10_001, -10_002}
    finally:
        config.GLOBAL_LLM_CONFIGS = original
