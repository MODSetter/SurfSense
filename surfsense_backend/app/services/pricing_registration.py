"""
Pricing registration with LiteLLM.

Many models reach our LiteLLM callback without LiteLLM knowing their
per-token cost — namely:

* The ~300 dynamic OpenRouter deployments (their pricing only lives on
  OpenRouter's ``/api/v1/models`` payload, never in LiteLLM's published
  pricing table).
* Static YAML deployments whose ``base_model`` name is operator-defined
  (e.g. custom Azure deployment names like ``gpt-5.4``) and therefore
  not in LiteLLM's table either.

Without registration, ``kwargs["response_cost"]`` is 0 for those calls
and the user gets billed nothing — a fail-safe but wrong answer for a
cost-based credit system. This module runs once at startup, after the
OpenRouter integration has fetched its catalogue, and registers each
known model's pricing with ``litellm.register_model()`` under multiple
plausible alias keys (LiteLLM's cost lookup may use any of them
depending on whether the call went through the Router, ChatLiteLLM,
or a direct ``acompletion``).

Operators who run a custom Azure deployment whose ``base_model`` name
isn't in LiteLLM's table can declare per-token pricing inline in
``global_llm_config.yaml`` via ``input_cost_per_token`` and
``output_cost_per_token`` (USD per token, e.g. ``0.000002``). Without
that declaration the model's calls debit 0 — never overbilled.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> float:
    """Return ``float(value)`` if it parses to a positive number, else 0.0."""
    if value is None:
        return 0.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return f if f > 0 else 0.0


def _alias_set_for_openrouter(model_id: str) -> list[str]:
    """Return the alias keys to register an OpenRouter model under.

    LiteLLM's cost-callback lookup key varies by call path:
    - Router with ``model="openrouter/X"`` → kwargs["model"] is
      typically ``openrouter/X``.
    - LiteLLM's own provider routing may strip the prefix and pass the
      bare ``X`` to the cost-table lookup.
    Registering under both keeps the lookup hermetic regardless of
    which path the call took.
    """
    aliases = [f"openrouter/{model_id}", model_id]
    return list(dict.fromkeys(a for a in aliases if a))


def _alias_set_for_yaml(provider: str, model_name: str, base_model: str) -> list[str]:
    """Return the alias keys to register a static YAML deployment under.

    Same reasoning as the OpenRouter set: cover the bare ``base_model``,
    the ``<provider>/<model>`` form LiteLLM Router constructs, and the
    bare ``model_name`` because callbacks sometimes see whichever was
    configured first.
    """
    provider_lower = (provider or "").lower()
    aliases: list[str] = []
    if base_model:
        aliases.append(base_model)
    if provider_lower and base_model:
        aliases.append(f"{provider_lower}/{base_model}")
    if model_name and model_name != base_model:
        aliases.append(model_name)
    if provider_lower and model_name and model_name != base_model:
        aliases.append(f"{provider_lower}/{model_name}")
    # Azure deployments often surface as "azure/<name>"; normalise the
    # ``azure_openai`` provider slug to the LiteLLM-canonical ``azure``.
    if provider_lower == "azure_openai":
        if base_model:
            aliases.append(f"azure/{base_model}")
        if model_name and model_name != base_model:
            aliases.append(f"azure/{model_name}")
    return list(dict.fromkeys(a for a in aliases if a))


def _register(
    aliases: list[str],
    *,
    input_cost: float,
    output_cost: float,
    provider: str,
    mode: str = "chat",
) -> int:
    """Register a single pricing entry under every alias in ``aliases``.

    Returns the count of aliases successfully registered.
    """
    payload: dict[str, dict[str, Any]] = {}
    for alias in aliases:
        payload[alias] = {
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "litellm_provider": provider,
            "mode": mode,
        }
    if not payload:
        return 0
    try:
        litellm.register_model(payload)
    except Exception as exc:
        logger.warning(
            "[PricingRegistration] register_model failed for aliases=%s: %s",
            aliases,
            exc,
        )
        return 0
    return len(payload)


def _register_chat_shape_configs(
    configs: list[dict],
    *,
    or_pricing: dict[str, dict[str, str]],
    label: str,
) -> tuple[int, int, int, list[str]]:
    """Common loop that registers per-token pricing for a list of "chat-shape"
    configs (chat or vision LLM — both use ``input_cost_per_token`` /
    ``output_cost_per_token`` and the LiteLLM ``mode="chat"`` cost shape).

    Returns ``(registered_models, registered_aliases, skipped, sample_keys)``.
    """
    registered_models = 0
    registered_aliases = 0
    skipped_no_pricing = 0
    sample_keys: list[str] = []

    for cfg in configs:
        provider = str(cfg.get("provider") or "").upper()
        model_name = str(cfg.get("model_name") or "").strip()
        litellm_params = cfg.get("litellm_params") or {}
        base_model = str(litellm_params.get("base_model") or model_name).strip()

        if provider == "OPENROUTER":
            entry = or_pricing.get(model_name)
            if entry:
                input_cost = _safe_float(entry.get("prompt"))
                output_cost = _safe_float(entry.get("completion"))
            else:
                # Vision configs from ``_generate_vision_llm_configs``
                # carry their pricing inline because the OpenRouter
                # raw-pricing cache is keyed by chat-catalogue model_id;
                # vision flows pick up the inline values here.
                input_cost = _safe_float(cfg.get("input_cost_per_token"))
                output_cost = _safe_float(cfg.get("output_cost_per_token"))
            if input_cost == 0.0 and output_cost == 0.0:
                skipped_no_pricing += 1
                continue
            aliases = _alias_set_for_openrouter(model_name)
            count = _register(
                aliases,
                input_cost=input_cost,
                output_cost=output_cost,
                provider="openrouter",
            )
            if count > 0:
                registered_models += 1
                registered_aliases += count
                if len(sample_keys) < 6:
                    sample_keys.extend(aliases[:2])
            continue

        input_cost = _safe_float(
            cfg.get("input_cost_per_token")
            or litellm_params.get("input_cost_per_token")
        )
        output_cost = _safe_float(
            cfg.get("output_cost_per_token")
            or litellm_params.get("output_cost_per_token")
        )
        if input_cost == 0.0 and output_cost == 0.0:
            skipped_no_pricing += 1
            continue
        aliases = _alias_set_for_yaml(provider, model_name, base_model)
        provider_slug = "azure" if provider == "AZURE_OPENAI" else provider.lower()
        count = _register(
            aliases,
            input_cost=input_cost,
            output_cost=output_cost,
            provider=provider_slug,
        )
        if count > 0:
            registered_models += 1
            registered_aliases += count
            if len(sample_keys) < 6:
                sample_keys.extend(aliases[:2])

    logger.info(
        "[PricingRegistration:%s] registered pricing for %d models (%d aliases); "
        "%d configs had no pricing data; sample registered keys=%s",
        label,
        registered_models,
        registered_aliases,
        skipped_no_pricing,
        sample_keys,
    )
    return registered_models, registered_aliases, skipped_no_pricing, sample_keys


def register_pricing_from_global_configs() -> None:
    """Register pricing for every known LLM deployment with LiteLLM.

    Walks ``config.GLOBAL_LLM_CONFIGS`` *and* ``config.GLOBAL_VISION_LLM_CONFIGS``
    so vision calls (during indexing) can resolve cost the same way chat
    calls do — namely:

    1. ``OPENROUTER``: pulls the cached raw pricing from
       ``OpenRouterIntegrationService`` (populated during its own
       startup fetch) and converts the per-token strings to floats. For
       vision configs that carry pricing inline (``input_cost_per_token`` /
       ``output_cost_per_token`` set on the cfg itself) we fall back to
       those values when the OR cache misses the model.
    2. Anything else: looks for operator-declared
       ``input_cost_per_token`` / ``output_cost_per_token`` on the YAML
       config block (top-level or nested under ``litellm_params``).

    **Image generation is intentionally NOT registered here.** The cost
    shape for image-gen is per-image (``output_cost_per_image``), not
    per-token, and LiteLLM's ``register_model`` doesn't accept those
    keys via the chat-cost path. OpenRouter image-gen models populate
    ``response_cost`` directly from their response header instead, and
    Azure-native image-gen models are already in LiteLLM's cost map.

    Calls without a resolved pair of costs are skipped, not registered
    with zeros — operators who forget pricing get a "$0 debit" warning
    in ``TokenTrackingCallback`` rather than silently overwriting any
    pricing LiteLLM might know natively.
    """
    from app.config import config as app_config

    chat_configs: list[dict] = list(getattr(app_config, "GLOBAL_LLM_CONFIGS", []) or [])
    vision_configs: list[dict] = list(
        getattr(app_config, "GLOBAL_VISION_LLM_CONFIGS", []) or []
    )
    if not chat_configs and not vision_configs:
        logger.info("[PricingRegistration] no global configs to register")
        return

    or_pricing: dict[str, dict[str, str]] = {}
    try:
        from app.services.openrouter_integration_service import (
            OpenRouterIntegrationService,
        )

        if OpenRouterIntegrationService.is_initialized():
            or_pricing = OpenRouterIntegrationService.get_instance().get_raw_pricing()
    except Exception as exc:
        logger.debug(
            "[PricingRegistration] OpenRouter pricing not available yet: %s", exc
        )

    if chat_configs:
        _register_chat_shape_configs(chat_configs, or_pricing=or_pricing, label="chat")
    if vision_configs:
        _register_chat_shape_configs(
            vision_configs, or_pricing=or_pricing, label="vision"
        )
