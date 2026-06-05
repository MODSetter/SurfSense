r"""LiteLLM-native prompt caching for SurfSense agents.

Replaces the legacy ``AnthropicPromptCachingMiddleware`` (its
``isinstance(model, ChatAnthropic)`` gate never matched our LiteLLM stack)
with LiteLLM's universal ``cache_control_injection_points`` mechanism, which
covers the Anthropic/Bedrock/Vertex/Gemini/OpenRouter/etc. marker-based
providers and the auto-caching OpenAI family.

Two breakpoints per request:

- ``index: 0`` pins the head-of-request system prompt. We use ``index: 0``,
  NOT ``role: system``: ``before_agent`` injectors accumulate many
  SystemMessages, and tagging all of them overflows Anthropic's 4-block cap
  (upstream 400 via OpenRouter).
- ``index: -1`` pins the latest message so longest-prefix lookup compounds
  multi-turn savings.

OpenAI-family configs also get ``prompt_cache_key`` (per-thread routing hint)
and ``prompt_cache_retention="24h"``. Azure is excluded from the latter
because LiteLLM's Azure transformer drops it (see
``_PROMPT_CACHE_RETENTION_PROVIDERS``).

Safety net: ``litellm.drop_params=True`` (set in ``app.services.llm_service``)
strips any kwarg the destination provider rejects, so an auto-mode fallback
can't 400 on these extras.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel

if TYPE_CHECKING:
    from app.agents.chat.runtime.llm_config import AgentConfig

logger = logging.getLogger(__name__)


# Head-of-request + latest message (see module docstring for the index:0 vs
# role:system rationale and Anthropic's 4-block cap).
_DEFAULT_INJECTION_POINTS: tuple[dict[str, Any], ...] = (
    {"location": "message", "index": 0},
    {"location": "message", "index": -1},
)

# Providers that accept the OpenAI ``prompt_cache_key`` routing hint. Strict
# whitelist: many providers route through litellm's ``openai`` prefix without
# the prompt-cache surface, so the prefix alone isn't enough to infer family.
_PROMPT_CACHE_KEY_PROVIDERS: frozenset[str] = frozenset(
    {"OPENAI", "DEEPSEEK", "XAI", "AZURE", "AZURE_OPENAI"}
)

# Subset that also accepts ``prompt_cache_retention="24h"``. Azure is excluded
# because LiteLLM's Azure transformer omits the param (drop_params strips it).
_PROMPT_CACHE_RETENTION_PROVIDERS: frozenset[str] = frozenset(
    {"OPENAI", "DEEPSEEK", "XAI"}
)


def _is_router_llm(llm: BaseChatModel) -> bool:
    """Detect ``ChatLiteLLMRouter`` by class name to avoid an import cycle."""
    return type(llm).__name__ == "ChatLiteLLMRouter"


def _provider_supports_prompt_cache_key(agent_config: AgentConfig | None) -> bool:
    """Whether the config targets a provider that accepts ``prompt_cache_key``.

    Strict — only returns True for explicitly chosen OPENAI, DEEPSEEK,
    XAI, AZURE, or AZURE_OPENAI providers. Auto-mode and custom
    providers return False because we can't statically know the
    destination and the router fans out across mixed providers.
    """
    if agent_config is None or not agent_config.provider:
        return False
    if agent_config.is_auto_mode:
        return False
    if agent_config.custom_provider:
        return False
    return agent_config.provider.upper() in _PROMPT_CACHE_KEY_PROVIDERS


def _provider_supports_prompt_cache_retention(
    agent_config: AgentConfig | None,
) -> bool:
    """Whether the config targets a provider that accepts ``prompt_cache_retention``.

    Tighter than :func:`_provider_supports_prompt_cache_key` — Azure
    deployments are excluded until LiteLLM ships the param in its Azure
    transformer (see module docstring).
    """
    if agent_config is None or not agent_config.provider:
        return False
    if agent_config.is_auto_mode:
        return False
    if agent_config.custom_provider:
        return False
    return agent_config.provider.upper() in _PROMPT_CACHE_RETENTION_PROVIDERS


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

    Idempotent (existing ``model_kwargs`` values are preserved) and mutates
    ``llm.model_kwargs`` in place. Without ``agent_config`` (or in auto-mode)
    only the universal injection points are set; ``thread_id`` adds a per-thread
    ``prompt_cache_key`` for OpenAI-family providers to improve routing affinity.
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

    # OpenAI-style extras only when the destination is statically known. The
    # auto-mode router fans out across mixed providers, so skip them there.
    if _is_router_llm(llm):
        return

    if (
        thread_id is not None
        and "prompt_cache_key" not in model_kwargs
        and _provider_supports_prompt_cache_key(agent_config)
    ):
        model_kwargs["prompt_cache_key"] = f"surfsense-thread-{thread_id}"

    if (
        "prompt_cache_retention" not in model_kwargs
        and _provider_supports_prompt_cache_retention(agent_config)
    ):
        model_kwargs["prompt_cache_retention"] = "24h"
