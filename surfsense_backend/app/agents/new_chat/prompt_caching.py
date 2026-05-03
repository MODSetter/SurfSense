"""LiteLLM-native prompt caching configuration for SurfSense agents.

Replaces the legacy ``AnthropicPromptCachingMiddleware`` (which never
activated for our LiteLLM-based stack — its ``isinstance(model, ChatAnthropic)``
gate always failed) with LiteLLM's universal caching mechanism.

Coverage:

- Marker-based providers (need ``cache_control`` injection, which LiteLLM
  performs automatically when ``cache_control_injection_points`` is set):
  ``anthropic/``, ``bedrock/``, ``vertex_ai/``, ``gemini/``, ``azure_ai/``,
  ``openrouter/`` (Claude/Gemini/MiniMax/GLM/z-ai routes), ``databricks/``
  (Claude), ``dashscope/`` (Qwen), ``minimax/``, ``zai/`` (GLM).
- Auto-cached (LiteLLM strips the marker silently): ``openai/``,
  ``deepseek/``, ``xai/`` — these caches automatically for prompts ≥1024
  tokens and surface ``prompt_cache_key`` / ``prompt_cache_retention``.

We inject **two** breakpoints per request:

- ``role: system`` — pins the SurfSense system prompt (provider variant,
  citation rules, tool catalog, KB tree, skills metadata) into the cache.
- ``index: -1`` — pins the latest message so multi-turn savings compound:
  Anthropic-family providers use longest-matching-prefix lookup, so turn
  N+1 still reads turn N's cache up to the shared prefix.

For OpenAI-family configs we additionally pass:

- ``prompt_cache_key=f"surfsense-thread-{thread_id}"`` — routing hint that
  raises hit rate by sending requests with a shared prefix to the same
  backend.
- ``prompt_cache_retention="24h"`` — extends cache TTL beyond the default
  5-10 min in-memory cache.

Safety net: ``litellm.drop_params=True`` is set globally in
``app.services.llm_service`` at module-load time. Any kwarg the destination
provider doesn't recognise is auto-stripped at the provider transformer
layer, so an OpenAI→Bedrock auto-mode fallback can't 400 on
``prompt_cache_key`` etc.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel

if TYPE_CHECKING:
    from app.agents.new_chat.llm_config import AgentConfig

logger = logging.getLogger(__name__)


# Two-breakpoint policy: system + latest message. See module docstring for
# rationale. Anthropic limits requests to 4 ``cache_control`` blocks; we
# use 2 here, leaving headroom for Phase-2 tool caching.
_DEFAULT_INJECTION_POINTS: tuple[dict[str, Any], ...] = (
    {"location": "message", "role": "system"},
    {"location": "message", "index": -1},
)

# Providers (uppercase ``AgentConfig.provider`` values) that natively expose
# OpenAI-style automatic prompt caching with ``prompt_cache_key`` and
# ``prompt_cache_retention`` kwargs. Strict whitelist — many other providers
# in ``PROVIDER_MAP`` route through litellm's ``openai`` prefix without
# implementing the OpenAI prompt-cache surface (e.g. MOONSHOT, ZHIPU,
# MINIMAX), so we can't infer family from the litellm prefix alone.
_OPENAI_FAMILY_PROVIDERS: frozenset[str] = frozenset({"OPENAI", "DEEPSEEK", "XAI"})


def _is_router_llm(llm: BaseChatModel) -> bool:
    """Detect ``ChatLiteLLMRouter`` (auto-mode) without an eager import.

    Importing ``app.services.llm_router_service`` at module-load time would
    create a cycle via ``llm_config -> prompt_caching -> llm_router_service``.
    Class-name comparison is sufficient since the class is defined in a
    single place.
    """
    return type(llm).__name__ == "ChatLiteLLMRouter"


def _is_openai_family_config(agent_config: AgentConfig | None) -> bool:
    """Whether the config targets an OpenAI-style prompt-cache surface.

    Strict — only returns True when the user explicitly chose OPENAI,
    DEEPSEEK, or XAI as the provider in their ``NewLLMConfig`` /
    ``YAMLConfig``. Auto-mode and custom providers return False because
    we can't statically know the destination.
    """
    if agent_config is None or not agent_config.provider:
        return False
    if agent_config.is_auto_mode:
        return False
    if agent_config.custom_provider:
        return False
    return agent_config.provider.upper() in _OPENAI_FAMILY_PROVIDERS


def _get_or_init_model_kwargs(llm: BaseChatModel) -> dict[str, Any] | None:
    """Return ``llm.model_kwargs`` as a writable dict, or ``None`` to bail.

    Initialises the field to ``{}`` when present-but-None on a Pydantic v2
    model. Returns ``None`` if the LLM type doesn't expose a writable
    ``model_kwargs`` attribute (caller should treat as no-op).
    """
    model_kwargs = getattr(llm, "model_kwargs", None)
    if isinstance(model_kwargs, dict):
        return model_kwargs
    try:
        llm.model_kwargs = {}  # type: ignore[attr-defined]
    except Exception:
        return None
    refreshed = getattr(llm, "model_kwargs", None)
    return refreshed if isinstance(refreshed, dict) else None


def apply_litellm_prompt_caching(
    llm: BaseChatModel,
    *,
    agent_config: AgentConfig | None = None,
    thread_id: int | None = None,
) -> None:
    """Configure LiteLLM prompt caching on a ChatLiteLLM/ChatLiteLLMRouter.

    Idempotent — values already present in ``llm.model_kwargs`` (e.g. from
    ``agent_config.litellm_params`` overrides) are preserved. Mutates
    ``llm.model_kwargs`` in place; the kwargs flow to ``litellm.completion``
    via ``ChatLiteLLM._default_params`` and via ``self.model_kwargs`` merge
    in our custom ``ChatLiteLLMRouter``.

    Args:
        llm: ChatLiteLLM, SanitizedChatLiteLLM, or ChatLiteLLMRouter instance.
        agent_config: Optional ``AgentConfig`` driving provider-specific
            behaviour. When omitted (or auto-mode), only the universal
            ``cache_control_injection_points`` are set.
        thread_id: Optional thread id used to construct a per-thread
            ``prompt_cache_key`` for OpenAI-family providers. Caching still
            works without it (server-side automatic), but the key improves
            backend routing affinity and therefore hit rate.
    """
    model_kwargs = _get_or_init_model_kwargs(llm)
    if model_kwargs is None:
        logger.debug(
            "apply_litellm_prompt_caching: %s exposes no writable model_kwargs; skipping",
            type(llm).__name__,
        )
        return

    if "cache_control_injection_points" not in model_kwargs:
        model_kwargs["cache_control_injection_points"] = [
            dict(point) for point in _DEFAULT_INJECTION_POINTS
        ]

    # OpenAI-family extras only when we statically know the destination is
    # OpenAI / DeepSeek / xAI. Auto-mode router fans out across providers
    # so we can't safely set OpenAI-only kwargs there (drop_params would
    # strip them but it's wasteful to set them in the first place).
    if _is_router_llm(llm):
        return
    if not _is_openai_family_config(agent_config):
        return

    if thread_id is not None and "prompt_cache_key" not in model_kwargs:
        model_kwargs["prompt_cache_key"] = f"surfsense-thread-{thread_id}"
    if "prompt_cache_retention" not in model_kwargs:
        model_kwargs["prompt_cache_retention"] = "24h"
