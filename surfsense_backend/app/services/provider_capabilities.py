"""Capability resolution shared by chat / image / vision call sites.

Why this exists
---------------
The chat catalog (YAML + dynamic OpenRouter + BYOK DB rows + Auto) needs a
single, authoritative answer to one question: *can this chat config accept
``image_url`` content blocks?* Without it, the new-chat selector can't badge
incompatible models and the streaming task can't fail fast with a friendly
error before sending an image to a text-only provider.

Two functions, two intents:

- :func:`derive_supports_image_input` — best-effort *True* for catalog and
  UI surfacing. Default-allow: an unknown / unmapped model is treated as
  capable so we never lock the user out of a freshly added or
  third-party-hosted vision model.

- :func:`is_known_text_only_chat_model` — strict opt-out for the streaming
  task's safety net. Returns True only when LiteLLM's model map *explicitly*
  sets ``supports_vision=False`` (or its bare-name variant does). Anything
  else — missing key, lookup exception, ``supports_vision=True`` — returns
  False so the request flows through to the provider.

Implementation rule: only public LiteLLM symbols
------------------------------------------------
``litellm.supports_vision`` and ``litellm.get_model_info`` are part of the
typed module surface (see ``litellm.__init__`` lazy stubs) and are stable
across releases. The private ``_is_explicitly_disabled_factory`` and
``_get_model_info_helper`` are intentionally avoided so a LiteLLM upgrade
can't silently break us.

Why the previous round's strict YAML opt-in flag failed
-------------------------------------------------------
``supports_image_input: false`` was the YAML loader's setdefault. Operators
maintaining ``global_llm_config.yaml`` never set it, so every Azure / OpenAI
YAML chat model — including vision-capable GPT-5.x and GPT-4o — resolved to
False and the streaming gate rejected every image turn. Sourcing capability
from LiteLLM's authoritative model map (which already says
``azure/gpt-5.4 -> supports_vision=true``) removes that operator toil.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import litellm

logger = logging.getLogger(__name__)


# Provider-name → LiteLLM model-prefix map.
#
# Owned here because ``app.services.provider_capabilities`` is the
# only edge that's safe to call from ``app.config``'s YAML loader at
# class-body init time. ``app.agents.new_chat.llm_config`` re-exports
# this constant under the historical ``PROVIDER_MAP`` name; placing the
# map there directly would re-introduce the
# ``app.config -> ... -> app.agents.new_chat.tools.generate_image ->
# app.config`` cycle that prompted the move.
_PROVIDER_PREFIX_MAP: dict[str, str] = {
    "OPENAI": "openai",
    "ANTHROPIC": "anthropic",
    "GROQ": "groq",
    "COHERE": "cohere",
    "GOOGLE": "gemini",
    "OLLAMA": "ollama_chat",
    "MISTRAL": "mistral",
    "AZURE_OPENAI": "azure",
    "OPENROUTER": "openrouter",
    "XAI": "xai",
    "BEDROCK": "bedrock",
    "VERTEX_AI": "vertex_ai",
    "TOGETHER_AI": "together_ai",
    "FIREWORKS_AI": "fireworks_ai",
    "DEEPSEEK": "openai",
    "ALIBABA_QWEN": "openai",
    "MOONSHOT": "openai",
    "ZHIPU": "openai",
    "GITHUB_MODELS": "github",
    "REPLICATE": "replicate",
    "PERPLEXITY": "perplexity",
    "ANYSCALE": "anyscale",
    "DEEPINFRA": "deepinfra",
    "CEREBRAS": "cerebras",
    "SAMBANOVA": "sambanova",
    "AI21": "ai21",
    "CLOUDFLARE": "cloudflare",
    "DATABRICKS": "databricks",
    "COMETAPI": "cometapi",
    "HUGGINGFACE": "huggingface",
    "MINIMAX": "openai",
    "CUSTOM": "custom",
}


def _candidate_model_strings(
    *,
    provider: str | None,
    model_name: str | None,
    base_model: str | None,
    custom_provider: str | None,
) -> list[tuple[str, str | None]]:
    """Return ``[(model_string, custom_llm_provider), ...]`` lookup candidates.

    LiteLLM's capability lookup is keyed by ``model`` + (optional)
    ``custom_llm_provider``. Different config sources give us different
    levels of detail, so we try the most-specific keys first and fall back
    to bare model names so unannotated entries (e.g. an Azure deployment
    pointing at ``gpt-5.4`` via ``litellm_params.base_model``) still hit the
    map. Order matters — the first lookup that returns a definitive answer
    wins for both helpers.
    """
    candidates: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()

    def _add(model: str | None, llm_provider: str | None) -> None:
        if not model:
            return
        key = (model, llm_provider)
        if key in seen:
            return
        seen.add(key)
        candidates.append(key)

    provider_prefix: str | None = None
    if provider:
        provider_prefix = _PROVIDER_PREFIX_MAP.get(provider.upper(), provider.lower())
    if custom_provider:
        # ``custom_provider`` overrides everything for CUSTOM/proxy setups.
        provider_prefix = custom_provider

    primary_model = base_model or model_name
    bare_model = model_name

    # Most-specific first: provider-prefixed identifier with explicit
    # custom_llm_provider so LiteLLM won't have to guess the provider via
    # ``get_llm_provider``.
    if primary_model and provider_prefix:
        # e.g. "azure/gpt-5.4" + custom_llm_provider="azure"
        if "/" in primary_model:
            _add(primary_model, provider_prefix)
        else:
            _add(f"{provider_prefix}/{primary_model}", provider_prefix)

    # Bare base_model (or model_name) with provider hint — handles entries
    # the upstream map keys without a provider prefix (most ``gpt-*`` and
    # ``claude-*`` entries do this).
    if primary_model:
        _add(primary_model, provider_prefix)

    # Fallback to model_name when base_model differs (e.g. an Azure
    # deployment whose model_name is the deployment id but base_model is the
    # canonical OpenAI sku).
    if bare_model and bare_model != primary_model:
        if provider_prefix and "/" not in bare_model:
            _add(f"{provider_prefix}/{bare_model}", provider_prefix)
        _add(bare_model, provider_prefix)
        _add(bare_model, None)

    return candidates


def derive_supports_image_input(
    *,
    provider: str | None = None,
    model_name: str | None = None,
    base_model: str | None = None,
    custom_provider: str | None = None,
    openrouter_input_modalities: Iterable[str] | None = None,
) -> bool:
    """Best-effort capability flag for the new-chat selector and catalog.

    Resolution order (first definitive answer wins):

    1. ``openrouter_input_modalities`` (when provided as a non-empty
       iterable). OpenRouter exposes ``architecture.input_modalities`` per
       model and that's the authoritative source for OR dynamic configs.
    2. ``litellm.supports_vision`` against each candidate identifier from
       :func:`_candidate_model_strings`. Returns True as soon as any
       candidate confirms vision support.
    3. Default ``True`` — the conservative-allow stance. An unknown /
       newly-added / third-party-hosted model is *not* pre-judged. The
       streaming safety net (:func:`is_known_text_only_chat_model`) is the
       only place a False ever blocks; everywhere else, a False here would
       just hide a usable model from the user.

    Returns:
        True if the model can plausibly accept image input, False only when
        OpenRouter explicitly says it can't.
    """
    if openrouter_input_modalities is not None:
        modalities = list(openrouter_input_modalities)
        if modalities:
            return "image" in modalities
        # Empty list explicitly published by OR — treat as "no image".
        return False

    for model_string, custom_llm_provider in _candidate_model_strings(
        provider=provider,
        model_name=model_name,
        base_model=base_model,
        custom_provider=custom_provider,
    ):
        try:
            if litellm.supports_vision(
                model=model_string, custom_llm_provider=custom_llm_provider
            ):
                return True
        except Exception as exc:
            logger.debug(
                "litellm.supports_vision raised for model=%s provider=%s: %s",
                model_string,
                custom_llm_provider,
                exc,
            )
            continue

    # Default-allow. ``is_known_text_only_chat_model`` is the strict gate.
    return True


def is_known_text_only_chat_model(
    *,
    provider: str | None = None,
    model_name: str | None = None,
    base_model: str | None = None,
    custom_provider: str | None = None,
) -> bool:
    """Strict opt-out probe for the streaming-task safety net.

    Returns True only when LiteLLM's model map *explicitly* sets
    ``supports_vision=False`` for at least one candidate identifier. Missing
    key, lookup exception, or ``supports_vision=True`` all return False so
    the streaming task lets the request through. This is the inverse-default
    of :func:`derive_supports_image_input`.

    Why two functions
    -----------------
    The selector wants "show me everything that's plausibly capable" —
    default-allow. The safety net wants "block only when I'm certain it
    can't" — default-pass. Mixing the two intents in a single function
    leads to the regression we're fixing here.
    """
    for model_string, custom_llm_provider in _candidate_model_strings(
        provider=provider,
        model_name=model_name,
        base_model=base_model,
        custom_provider=custom_provider,
    ):
        try:
            info = litellm.get_model_info(
                model=model_string, custom_llm_provider=custom_llm_provider
            )
        except Exception as exc:
            logger.debug(
                "litellm.get_model_info raised for model=%s provider=%s: %s",
                model_string,
                custom_llm_provider,
                exc,
            )
            continue

        # ``ModelInfo`` is a TypedDict (dict at runtime). ``supports_vision``
        # may be missing, None, True, or False. We only fire on explicit
        # False — None / missing / True all mean "don't block".
        try:
            value = info.get("supports_vision")  # type: ignore[union-attr]
        except AttributeError:
            value = None
        if value is False:
            return True

    return False


__all__ = [
    "derive_supports_image_input",
    "is_known_text_only_chat_model",
]
