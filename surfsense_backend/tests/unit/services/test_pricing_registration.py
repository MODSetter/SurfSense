"""Pricing registration unit tests.

The pricing-registration module is what makes ``response_cost`` populate
correctly for OpenRouter dynamic models and operator-defined Azure
deployments — both of which LiteLLM doesn't natively know about. The tests
exercise:

* The alias generators emit every shape that LiteLLM's cost-callback might
  use (``openrouter/X`` and bare ``X``; YAML-defined ``base_model``,
  ``provider/base_model``, ``provider/model_name``, plus the special
  ``azure_openai`` → ``azure`` normalisation).
* ``register_pricing_from_global_configs`` calls ``litellm.register_model``
  with the right alias set and pricing values per provider.
* Configs without a resolvable pair of cost values are skipped — never
  registered as zero, since that would override pricing LiteLLM might
  already know natively.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Alias generators
# ---------------------------------------------------------------------------


def test_openrouter_alias_set_includes_prefixed_and_bare():
    from app.services.pricing_registration import _alias_set_for_openrouter

    aliases = _alias_set_for_openrouter("anthropic/claude-3-5-sonnet")
    assert aliases == [
        "openrouter/anthropic/claude-3-5-sonnet",
        "anthropic/claude-3-5-sonnet",
    ]


def test_openrouter_alias_set_dedupes():
    """If the model id is already prefixed with ``openrouter/``, the alias
    set must not contain duplicates that would re-register the same key
    twice.
    """
    from app.services.pricing_registration import _alias_set_for_openrouter

    aliases = _alias_set_for_openrouter("openrouter/foo")
    # The bare and prefixed variants compute to the same string here, so we
    # at minimum require uniqueness.
    assert len(aliases) == len(set(aliases))


def test_yaml_alias_set_for_azure_openai_normalises_to_azure():
    """``azure_openai`` (our YAML provider slug) must register under
    ``azure/<name>`` so the LiteLLM Router's deployment-resolution path
    (which uses provider ``azure``) finds the pricing too.
    """
    from app.services.pricing_registration import _alias_set_for_yaml

    aliases = _alias_set_for_yaml(
        provider="AZURE_OPENAI",
        model_name="gpt-5.4",
        base_model="gpt-5.4",
    )
    assert "gpt-5.4" in aliases
    assert "azure_openai/gpt-5.4" in aliases
    assert "azure/gpt-5.4" in aliases


def test_yaml_alias_set_distinguishes_model_name_and_base_model():
    """When ``model_name`` differs from ``base_model`` (operator labelled a
    deployment), both must appear in the alias set since either may surface
    in callbacks depending on the call path.
    """
    from app.services.pricing_registration import _alias_set_for_yaml

    aliases = _alias_set_for_yaml(
        provider="OPENAI",
        model_name="my-deployment-label",
        base_model="gpt-4o",
    )
    assert "gpt-4o" in aliases
    assert "openai/gpt-4o" in aliases
    assert "my-deployment-label" in aliases
    assert "openai/my-deployment-label" in aliases


def test_yaml_alias_set_omits_provider_prefix_when_provider_blank():
    from app.services.pricing_registration import _alias_set_for_yaml

    aliases = _alias_set_for_yaml(
        provider="",
        model_name="foo",
        base_model="bar",
    )
    assert "bar" in aliases
    assert "foo" in aliases
    assert all("/" not in a for a in aliases)


# ---------------------------------------------------------------------------
# register_pricing_from_global_configs
# ---------------------------------------------------------------------------


class _RegistrationSpy:
    """Captures the dicts passed to ``litellm.register_model``.

    Many calls may go through; we just record them all and let tests assert
    against the union.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.calls.append(payload)

    @property
    def all_keys(self) -> set[str]:
        keys: set[str] = set()
        for payload in self.calls:
            keys.update(payload.keys())
        return keys


def _patch_register(monkeypatch: pytest.MonkeyPatch) -> _RegistrationSpy:
    spy = _RegistrationSpy()
    monkeypatch.setattr(
        "app.services.pricing_registration.litellm.register_model",
        spy,
        raising=False,
    )
    return spy


def _patch_openrouter_pricing(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, dict[str, str]]
) -> None:
    """Pretend the OpenRouter integration is initialised with ``mapping``."""

    class _Stub:
        def get_raw_pricing(self) -> dict[str, dict[str, str]]:
            return mapping

    class _StubService:
        @classmethod
        def is_initialized(cls) -> bool:
            return True

        @classmethod
        def get_instance(cls) -> _Stub:
            return _Stub()

    monkeypatch.setattr(
        "app.services.openrouter_integration_service.OpenRouterIntegrationService",
        _StubService,
        raising=False,
    )


def test_openrouter_models_register_under_aliases(monkeypatch):
    """An OpenRouter config whose ``model_name`` is in the cached raw
    pricing map is registered under both ``openrouter/X`` and bare ``X``.
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(
        monkeypatch,
        {
            "anthropic/claude-3-5-sonnet": {
                "prompt": "0.000003",
                "completion": "0.000015",
            }
        },
    )

    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": 1,
                "provider": "OPENROUTER",
                "model_name": "anthropic/claude-3-5-sonnet",
            }
        ],
    )

    register_pricing_from_global_configs()

    assert "openrouter/anthropic/claude-3-5-sonnet" in spy.all_keys
    assert "anthropic/claude-3-5-sonnet" in spy.all_keys
    # Costs are float-converted from the raw OpenRouter strings.
    payload = spy.calls[0]
    assert payload["openrouter/anthropic/claude-3-5-sonnet"][
        "input_cost_per_token"
    ] == pytest.approx(3e-6)
    assert payload["openrouter/anthropic/claude-3-5-sonnet"][
        "output_cost_per_token"
    ] == pytest.approx(15e-6)
    assert (
        payload["openrouter/anthropic/claude-3-5-sonnet"]["litellm_provider"]
        == "openrouter"
    )


def test_yaml_override_registers_under_alias_set(monkeypatch):
    """Operator-declared ``input_cost_per_token`` /
    ``output_cost_per_token`` on a YAML config registers under every
    alias the YAML alias generator produces — including the ``azure/``
    normalisation for ``azure_openai`` providers.
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(monkeypatch, {})

    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": 1,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5.4",
                "litellm_params": {
                    "base_model": "gpt-5.4",
                    "input_cost_per_token": 2e-6,
                    "output_cost_per_token": 8e-6,
                },
            }
        ],
    )

    register_pricing_from_global_configs()

    keys = spy.all_keys
    assert "gpt-5.4" in keys
    assert "azure_openai/gpt-5.4" in keys
    assert "azure/gpt-5.4" in keys

    payload = spy.calls[0]
    entry = payload["gpt-5.4"]
    assert entry["input_cost_per_token"] == pytest.approx(2e-6)
    assert entry["output_cost_per_token"] == pytest.approx(8e-6)
    assert entry["litellm_provider"] == "azure"


def test_no_override_means_no_registration(monkeypatch):
    """A YAML config that *omits* both pricing fields must NOT be registered
    — registering as zero would override LiteLLM's native pricing for the
    ``base_model`` key (e.g. ``gpt-4o``) and silently make every user's
    bill drop to $0. Fail-safe is "skip and warn", not "register zero".
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(monkeypatch, {})

    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": 1,
                "provider": "OPENAI",
                "model_name": "gpt-4o",
                "litellm_params": {"base_model": "gpt-4o"},
            }
        ],
    )

    register_pricing_from_global_configs()

    assert spy.calls == []


def test_openrouter_skipped_when_pricing_missing(monkeypatch):
    """If the OpenRouter raw-pricing cache doesn't carry an entry for a
    configured model (network blip during refresh, model added later, etc.),
    we skip it rather than registering zero pricing.
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(
        monkeypatch, {"some/other-model": {"prompt": "1", "completion": "1"}}
    )

    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": 1,
                "provider": "OPENROUTER",
                "model_name": "anthropic/claude-3-5-sonnet",
            }
        ],
    )

    register_pricing_from_global_configs()

    assert spy.calls == []


def test_register_continues_after_individual_failure(monkeypatch, caplog):
    """A single bad ``register_model`` call (e.g. raising LiteLLM error)
    must not abort registration of the remaining configs.
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    failing_keys: set[str] = {"anthropic/claude-3-5-sonnet"}
    successful_calls: list[dict[str, Any]] = []

    def _maybe_fail(payload: dict[str, Any]) -> None:
        if any(k in failing_keys for k in payload):
            raise RuntimeError("boom")
        successful_calls.append(payload)

    monkeypatch.setattr(
        "app.services.pricing_registration.litellm.register_model",
        _maybe_fail,
        raising=False,
    )
    _patch_openrouter_pricing(
        monkeypatch,
        {
            "anthropic/claude-3-5-sonnet": {
                "prompt": "0.000003",
                "completion": "0.000015",
            }
        },
    )

    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": 1,
                "provider": "OPENROUTER",
                "model_name": "anthropic/claude-3-5-sonnet",
            },
            {
                "id": 2,
                "provider": "OPENAI",
                "model_name": "custom-deployment",
                "litellm_params": {
                    "base_model": "custom-deployment",
                    "input_cost_per_token": 1e-6,
                    "output_cost_per_token": 2e-6,
                },
            },
        ],
    )

    register_pricing_from_global_configs()

    # The good config still registered.
    assert any("custom-deployment" in payload for payload in successful_calls)


def test_vision_configs_registered_with_chat_shape(monkeypatch):
    """``register_pricing_from_global_configs`` walks
    ``GLOBAL_VISION_LLM_CONFIGS`` in addition to the chat configs so vision
    calls (during indexing) bill correctly. Vision configs use the same
    chat-shape token prices, but image-gen pricing is intentionally NOT
    registered here (handled via ``response_cost`` in LiteLLM).
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(
        monkeypatch,
        {"openai/gpt-4o": {"prompt": "0.000005", "completion": "0.000015"}},
    )

    # No chat configs — only vision. Proves the vision walk is a separate
    # iteration, not piggy-backed on the chat list.
    monkeypatch.setattr(config, "GLOBAL_LLM_CONFIGS", [])
    monkeypatch.setattr(
        config,
        "GLOBAL_VISION_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "openai/gpt-4o",
                "billing_tier": "premium",
                "input_cost_per_token": 5e-6,
                "output_cost_per_token": 15e-6,
            }
        ],
    )

    register_pricing_from_global_configs()

    assert "openrouter/openai/gpt-4o" in spy.all_keys
    payload_value = spy.calls[0]["openrouter/openai/gpt-4o"]
    assert payload_value["mode"] == "chat"
    assert payload_value["litellm_provider"] == "openrouter"
    assert payload_value["input_cost_per_token"] == pytest.approx(5e-6)
    assert payload_value["output_cost_per_token"] == pytest.approx(15e-6)


def test_vision_with_inline_pricing_when_or_cache_missing(monkeypatch):
    """If the OpenRouter pricing cache misses a vision model (different
    catalogue surface), the vision walk falls back to inline
    ``input_cost_per_token``/``output_cost_per_token`` on the cfg itself.
    """
    from app.config import config
    from app.services.pricing_registration import register_pricing_from_global_configs

    spy = _patch_register(monkeypatch)
    _patch_openrouter_pricing(monkeypatch, {})

    monkeypatch.setattr(config, "GLOBAL_LLM_CONFIGS", [])
    monkeypatch.setattr(
        config,
        "GLOBAL_VISION_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-2.5-flash",
                "billing_tier": "premium",
                "input_cost_per_token": 1e-6,
                "output_cost_per_token": 4e-6,
            }
        ],
    )

    register_pricing_from_global_configs()

    assert "openrouter/google/gemini-2.5-flash" in spy.all_keys
