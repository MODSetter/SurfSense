"""Image-aware extension of the Auto-pin resolver.

When the current chat turn carries an ``image_url`` block, the pin
resolver must:

1. Filter the candidate pool to vision-capable cfgs so a freshly
   selected pin can never be text-only.
2. Treat any existing pin whose capability is False as invalid (force
   re-pin), even when it would otherwise be reused as the thread's
   stable model.
3. Raise ``ValueError`` (mapped to the friendly
   ``MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT`` SSE error in the streaming
   task) when no vision-capable cfg is available — instead of silently
   pinning text-only and 404-ing at the provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.services.auto_model_pin_service import (
    clear_healthy,
    clear_runtime_cooldown,
    resolve_or_get_pinned_llm_config_id,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_caches():
    clear_runtime_cooldown()
    clear_healthy()
    yield
    clear_runtime_cooldown()
    clear_healthy()


@dataclass
class _FakeQuotaResult:
    allowed: bool


class _FakeExecResult:
    def __init__(self, *, thread=None, scalars=None):
        self._thread = thread
        self._scalars = scalars or []

    def unique(self):
        return self

    def scalar_one_or_none(self):
        return self._thread

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars)


class _FakeSession:
    def __init__(self, thread):
        self.thread = thread
        self.commit_count = 0
        self.execute_count = 0

    async def execute(self, _stmt):
        self.execute_count += 1
        if self.execute_count == 1:
            return _FakeExecResult(thread=self.thread)
        return _FakeExecResult(scalars=[])

    async def commit(self):
        self.commit_count += 1


def _thread(*, pinned: int | None = None):
    return SimpleNamespace(id=1, search_space_id=10, pinned_llm_config_id=pinned)


def _set_global_llm_configs(monkeypatch, config, configs: list[dict]):
    from app.services.provider_capabilities import derive_supports_image_input

    connections = []
    models = []
    for cfg in configs:
        config_id = int(cfg["id"])
        connection_id = config_id - 100_000
        provider = cfg.get("provider") or cfg.get("litellm_provider")
        model_name = cfg["model_name"]
        if "supports_image_input" not in cfg:
            litellm_params = cfg.get("litellm_params") or {}
            base_model = (
                litellm_params.get("base_model")
                if isinstance(litellm_params, dict)
                else None
            )
            cfg["supports_image_input"] = derive_supports_image_input(
                provider=provider,
                model_name=model_name,
                base_model=base_model,
                custom_provider=cfg.get("custom_provider"),
            )
        connections.append(
            {
                "id": connection_id,
                "provider": provider,
                "scope": "GLOBAL",
                "enabled": True,
            }
        )
        model = {
            "id": config_id,
            "connection_id": connection_id,
            "model_id": model_name,
            "display_name": cfg.get("name") or model_name,
            "supports_chat": cfg.get("supports_chat", True),
            "supports_tools": cfg.get("supports_tools", True),
            "supports_image_generation": cfg.get("supports_image_generation", False),
            "capabilities_override": cfg.get("capabilities_override") or {},
            "billing_tier": cfg.get("billing_tier", "free"),
            "catalog": {
                "auto_pin_tier": cfg.get("auto_pin_tier"),
                "quality_score": cfg.get("quality_score"),
            },
            "supports_image_input": cfg["supports_image_input"],
        }
        models.append(model)

    monkeypatch.setattr(config, "GLOBAL_LLM_CONFIGS", configs)
    monkeypatch.setattr(config, "GLOBAL_CONNECTIONS", connections)
    monkeypatch.setattr(config, "GLOBAL_MODELS", models)


def _vision_cfg(id_: int, *, tier: str = "free", quality: int = 80) -> dict:
    return {
        "id": id_,
        "litellm_provider": "openai",
        "model_name": f"vision-{id_}",
        "api_key": "k",
        "billing_tier": tier,
        "supports_image_input": True,
        "auto_pin_tier": "A",
        "quality_score": quality,
    }


def _text_only_cfg(id_: int, *, tier: str = "free", quality: int = 90) -> dict:
    return {
        "id": id_,
        "litellm_provider": "openai",
        "model_name": f"text-{id_}",
        "api_key": "k",
        "billing_tier": tier,
        # Higher quality than the vision cfgs — so a bug that ignores
        # the image flag would surface as the resolver picking this one.
        "supports_image_input": False,
        "auto_pin_tier": "A",
        "quality_score": quality,
    }


async def _premium_allowed(*_args, **_kwargs):
    return _FakeQuotaResult(allowed=True)


@pytest.mark.asyncio
async def test_image_turn_filters_out_text_only_candidates(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread())
    _set_global_llm_configs(monkeypatch, config, [_text_only_cfg(-1), _vision_cfg(-2)])
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id=None,
        selected_llm_config_id=0,
        requires_image_input=True,
    )

    assert result.resolved_llm_config_id == -2
    # The thread should be pinned to the vision cfg even though the
    # text-only cfg has a higher quality score.
    assert session.thread.pinned_llm_config_id == -2


@pytest.mark.asyncio
async def test_image_turn_force_repins_stale_text_only_pin(monkeypatch):
    """An existing text-only pin must be invalidated when the next turn
    requires image input. The non-image path would happily reuse it."""
    from app.config import config

    session = _FakeSession(_thread(pinned=-1))
    _set_global_llm_configs(monkeypatch, config, [_text_only_cfg(-1), _vision_cfg(-2)])
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id=None,
        selected_llm_config_id=0,
        requires_image_input=True,
    )

    assert result.resolved_llm_config_id == -2
    assert result.from_existing_pin is False
    assert session.thread.pinned_llm_config_id == -2


@pytest.mark.asyncio
async def test_image_turn_reuses_existing_vision_pin(monkeypatch):
    """If the thread is already pinned to a vision-capable cfg, reuse it
    — same as the non-image path. Image-aware filtering must not force
    spurious re-pins."""
    from app.config import config

    session = _FakeSession(_thread(pinned=-2))
    _set_global_llm_configs(
        monkeypatch,
        config,
        [_text_only_cfg(-1), _vision_cfg(-2), _vision_cfg(-3, quality=70)],
    )
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id=None,
        selected_llm_config_id=0,
        requires_image_input=True,
    )

    assert result.resolved_llm_config_id == -2
    assert result.from_existing_pin is True


@pytest.mark.asyncio
async def test_image_turn_with_no_vision_candidates_raises(monkeypatch):
    """The friendly-error path: no vision-capable cfg in the pool -> raise
    ``ValueError`` whose message contains ``vision-capable`` so the
    streaming task can map it to ``MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT``."""
    from app.config import config

    session = _FakeSession(_thread())
    _set_global_llm_configs(
        monkeypatch, config, [_text_only_cfg(-1), _text_only_cfg(-2)]
    )
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    with pytest.raises(ValueError, match="vision-capable"):
        await resolve_or_get_pinned_llm_config_id(
            session,
            thread_id=1,
            search_space_id=10,
            user_id=None,
            selected_llm_config_id=0,
            requires_image_input=True,
        )


@pytest.mark.asyncio
async def test_non_image_turn_keeps_text_only_in_pool(monkeypatch):
    """Regression guard: the image flag must default False and not affect
    a normal text-only turn — text-only cfgs remain selectable."""
    from app.config import config

    session = _FakeSession(_thread())
    _set_global_llm_configs(monkeypatch, config, [_text_only_cfg(-1)])
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id=None,
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -1


@pytest.mark.asyncio
async def test_image_turn_unannotated_cfg_resolves_via_helper(monkeypatch):
    """A YAML cfg that omits ``supports_image_input`` falls through to
    ``derive_supports_image_input`` (LiteLLM-driven). For ``gpt-4o``
    that returns True, so the cfg should be a valid candidate."""
    from app.config import config

    session = _FakeSession(_thread())
    cfg_unannotated_vision = {
        "id": -2,
        "litellm_provider": "openai",
        "model_name": "gpt-4o",  # known vision model in LiteLLM map
        "api_key": "k",
        "billing_tier": "free",
        "auto_pin_tier": "A",
        "quality_score": 80,
        # NOTE: no supports_image_input key
    }
    _set_global_llm_configs(monkeypatch, config, [cfg_unannotated_vision])
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        _premium_allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id=None,
        selected_llm_config_id=0,
        requires_image_input=True,
    )
    assert result.resolved_llm_config_id == -2
