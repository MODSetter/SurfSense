"""Provider-aware ``api_base`` resolution shared by chat / image-gen / vision.

LiteLLM falls back to the module-global ``litellm.api_base`` when an
individual call doesn't pass one, which silently inherits provider-agnostic
env vars like ``AZURE_OPENAI_ENDPOINT`` / ``OPENAI_API_BASE``. Without an
explicit ``api_base``, an ``openrouter/<model>`` request can end up at an
Azure endpoint and 404 with ``Resource not found`` (real reproducer:
[litellm/llms/openrouter/image_generation/transformation.py:242-263] appends
``/chat/completions`` to whatever inherited base it gets, regardless of
provider).

The chat router has had this defense for a while
(``llm_router_service.py:466-478``). This module hoists the maps + cascade
into a tiny standalone helper so vision and image-gen can share the same
source of truth without an inter-service circular import.
"""

from __future__ import annotations


PROVIDER_DEFAULT_API_BASE: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "perplexity": "https://api.perplexity.ai",
    "xai": "https://api.x.ai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "fireworks_ai": "https://api.fireworks.ai/inference/v1",
    "together_ai": "https://api.together.xyz/v1",
    "anyscale": "https://api.endpoints.anyscale.com/v1",
    "cometapi": "https://api.cometapi.com/v1",
    "sambanova": "https://api.sambanova.ai/v1",
}
"""Default ``api_base`` per LiteLLM provider prefix (lowercase).

Only providers with a well-known, stable public base URL are listed —
self-hosted / BYO-endpoint providers (ollama, custom, bedrock, vertex_ai,
huggingface, databricks, cloudflare, replicate) are intentionally omitted
so their existing config-driven behaviour is preserved."""


PROVIDER_KEY_DEFAULT_API_BASE: dict[str, str] = {
    "DEEPSEEK": "https://api.deepseek.com/v1",
    "ALIBABA_QWEN": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "MOONSHOT": "https://api.moonshot.ai/v1",
    "ZHIPU": "https://open.bigmodel.cn/api/paas/v4",
    "MINIMAX": "https://api.minimax.io/v1",
}
"""Canonical provider key (uppercase) → base URL.

Used when the LiteLLM provider prefix is the generic ``openai`` shim but the
config's ``provider`` field tells us which API it actually is (DeepSeek,
Alibaba, Moonshot, Zhipu, MiniMax all use the ``openai`` prefix but each
has its own base URL)."""


def resolve_api_base(
    *,
    provider: str | None,
    provider_prefix: str | None,
    config_api_base: str | None,
) -> str | None:
    """Resolve a non-Azure-leaking ``api_base`` for a deployment.

    Cascade (first non-empty wins):
      1. The config's own ``api_base`` (whitespace-only treated as missing).
      2. ``PROVIDER_KEY_DEFAULT_API_BASE[provider.upper()]``.
      3. ``PROVIDER_DEFAULT_API_BASE[provider_prefix.lower()]``.
      4. ``None`` — caller should NOT set ``api_base`` and let the LiteLLM
         provider integration apply its own default (e.g. AzureOpenAI's
         deployment-derived URL, custom provider's per-deployment URL).

    Args:
        provider: The config's ``provider`` field (e.g. ``"OPENROUTER"``,
            ``"DEEPSEEK"``). Case-insensitive.
        provider_prefix: The LiteLLM model-string prefix the same call
            site builds for the model id (e.g. ``"openrouter"``,
            ``"groq"``). Case-insensitive.
        config_api_base: ``api_base`` from the global YAML / DB row /
            OpenRouter dynamic config. Empty / whitespace-only means
            "missing" — the resolver still applies the cascade.

    Returns:
        A URL string, or ``None`` if no default applies for this provider.
    """
    if config_api_base and config_api_base.strip():
        return config_api_base

    if provider:
        key_default = PROVIDER_KEY_DEFAULT_API_BASE.get(provider.upper())
        if key_default:
            return key_default

    if provider_prefix:
        prefix_default = PROVIDER_DEFAULT_API_BASE.get(provider_prefix.lower())
        if prefix_default:
            return prefix_default

    return None


__all__ = [
    "PROVIDER_DEFAULT_API_BASE",
    "PROVIDER_KEY_DEFAULT_API_BASE",
    "resolve_api_base",
]
