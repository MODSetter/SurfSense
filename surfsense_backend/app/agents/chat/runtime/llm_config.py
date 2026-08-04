"""
LLM configuration utilities for SurfSense agents.

This module provides functions for loading LLM configurations from:
1. Auto mode (ID 0) - Resolved by callers to a concrete model-connection model
2. YAML files (global configs with negative IDs)
3. Database model-connections table (user-created configs with positive IDs)

It also provides utilities for creating ChatLiteLLM instances and
managing prompt configurations.
"""

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_litellm import ChatLiteLLM
from litellm import get_model_info

from app.agents.chat.runtime.prompt_caching import (
    apply_litellm_prompt_caching,
)
from app.services.context_admission import (
    SURFSENSE_UNKNOWN_MODEL_MAX_INPUT_TOKENS,
    admit_langchain_messages,
    compute_tool_tokens,
)
from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    _sanitize_content,
)


def _sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Sanitize content on every message so it is safe for any provider.

    Handles three cross-provider incompatibilities:
    - List content with provider-specific blocks (e.g. ``thinking``)
    - List content with bare strings or empty text blocks
    - AI messages with empty content + tool calls: some providers (Bedrock)
      convert ``""`` to ``[{"type":"text","text":""}]`` server-side then
      reject the blank text.  The OpenAI spec says ``content`` should be
      ``null`` when an assistant message only carries tool calls.
    """
    sanitized: list[BaseMessage] = []
    for msg in messages:
        next_msg = msg.model_copy(deep=True)
        if isinstance(next_msg.content, list):
            next_msg.content = _sanitize_content(next_msg.content)
        if (
            isinstance(next_msg, AIMessage)
            and (not next_msg.content or next_msg.content == "")
            and getattr(next_msg, "tool_calls", None)
        ):
            next_msg.content = None  # type: ignore[assignment]
        sanitized.append(next_msg)
    return sanitized


class SanitizedChatLiteLLM(ChatLiteLLM):
    """ChatLiteLLM subclass that strips provider-specific content blocks
    (e.g. ``thinking`` from reasoning models) and normalises bare strings
    in content arrays before forwarding to the underlying provider."""

    def _count_context_tokens(self, messages: list[dict[str, Any]]) -> int | None:
        from litellm import token_counter

        profile = getattr(self, "profile", None)
        if not isinstance(profile, dict):
            return None
        model_names = profile.get("token_count_models")
        if not isinstance(model_names, list):
            model_names = [profile.get("token_count_model")]
        counts: list[int] = []
        for model_name in model_names:
            if not isinstance(model_name, str) or not model_name:
                continue
            try:
                counts.append(token_counter(messages=messages, model=model_name))
            except Exception:
                continue
        return max(counts) if counts else None

    def _admit_messages(
        self, messages: list[BaseMessage], tools: Any = None
    ) -> list[BaseMessage]:
        sanitized = _sanitize_messages(messages)
        profile = getattr(self, "profile", None)
        max_input_tokens = (
            profile.get("max_input_tokens") if isinstance(profile, dict) else None
        )
        if (
            not isinstance(max_input_tokens, int)
            or isinstance(max_input_tokens, bool)
            or max_input_tokens <= 0
        ):
            return sanitized
        return admit_langchain_messages(
            sanitized,
            sanitize_content=_sanitize_content,
            count_tokens=self._count_context_tokens,
            max_input_tokens=max_input_tokens,
            reserved_tokens=compute_tool_tokens(tools, self._count_context_tokens),
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return super()._generate(
            self._admit_messages(messages, kwargs.get("tools")),
            stop,
            run_manager,
            **kwargs,
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        yield from super()._stream(
            self._admit_messages(messages, kwargs.get("tools")),
            stop,
            run_manager,
            **kwargs,
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        async for chunk in super()._astream(
            self._admit_messages(messages, kwargs.get("tools")),
            stop,
            run_manager,
            **kwargs,
        ):
            yield chunk

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await super()._agenerate(
            self._admit_messages(messages, kwargs.get("tools")),
            stop=stop,
            run_manager=run_manager,
            stream=stream,
            **kwargs,
        )


def resolve_max_input_tokens(
    model_string: str,
    persisted_max_input_tokens: int | None = None,
) -> int:
    """Resolve the model budget: stored limit, then catalog, then fallback.

    Deliberately ignores how much context a local runtime currently has
    loaded: LM Studio and Ollama load, unload, and JIT-reload instances at
    will, so any value we could read here goes stale between requests. A
    runtime whose loaded context is smaller than this budget rejects the
    request itself, and that error is classified as MODEL_CONTEXT_LIMIT.
    """
    if (
        isinstance(persisted_max_input_tokens, int)
        and not isinstance(persisted_max_input_tokens, bool)
        and persisted_max_input_tokens > 0
    ):
        return persisted_max_input_tokens

    try:
        catalog_value = get_model_info(model_string).get("max_input_tokens")
        if (
            isinstance(catalog_value, int)
            and not isinstance(catalog_value, bool)
            and catalog_value > 0
        ):
            return catalog_value
    except Exception:
        pass
    return SURFSENSE_UNKNOWN_MODEL_MAX_INPUT_TOKENS


def _attach_model_profile(
    llm: ChatLiteLLM,
    model_string: str,
    persisted_max_input_tokens: int | None = None,
) -> int:
    """Attach normalized context metadata and return the effective limit."""
    max_input_tokens = resolve_max_input_tokens(
        model_string,
        persisted_max_input_tokens=persisted_max_input_tokens,
    )
    llm.profile = {
        "max_input_tokens": max_input_tokens,
        "max_input_tokens_upper": max_input_tokens,
        "token_count_model": model_string,
        "token_count_models": [model_string],
    }
    return max_input_tokens


@dataclass
class AgentConfig:
    """
    Complete configuration for the SurfSense agent.

    This combines resolved model settings with prompt configuration.
    Supports Auto mode metadata (ID 0). Runtime callers must resolve Auto to
    a concrete global or BYOK model before constructing ChatLiteLLM.
    """

    # LLM Model Settings
    provider: str
    model_name: str
    api_key: str
    api_base: str | None = None
    custom_provider: str | None = None
    litellm_params: dict | None = None

    # Prompt Configuration
    system_instructions: str | None = None
    use_default_system_instructions: bool = True
    citations_enabled: bool = True

    # Metadata
    config_id: int | None = None
    config_name: str | None = None

    # Auto mode flag
    is_auto_mode: bool = False

    # Token quota and policy
    billing_tier: str = "free"
    is_premium: bool = False
    anonymous_enabled: bool = False
    quota_reserve_tokens: int | None = None

    # Default-allow: only the streaming safety net (is_known_text_only_chat_model)
    # actually blocks on False, so defaulting False would silently hide
    # vision-capable models. Resolved via derive_supports_image_input.
    supports_image_input: bool = True

    @classmethod
    def from_auto_mode(cls) -> "AgentConfig":
        """Build an AgentConfig for Auto mode (LiteLLM Router load balancing)."""
        return cls(
            provider="AUTO",
            model_name="auto",
            api_key="",  # Not needed for router
            api_base=None,
            custom_provider=None,
            litellm_params=None,
            system_instructions=None,
            use_default_system_instructions=True,
            citations_enabled=True,
            config_id=AUTO_MODE_ID,
            config_name="Auto",
            is_auto_mode=True,
            billing_tier="free",
            is_premium=False,
            anonymous_enabled=False,
            quota_reserve_tokens=None,
            # Auto fails over across the pool, so a non-vision deployment's 404
            # is just an allowed_fails event rather than a hard block.
            supports_image_input=True,
        )

    @classmethod
    def from_yaml_config(cls, yaml_config: dict) -> "AgentConfig":
        """Build an AgentConfig from a YAML configuration dictionary.

        Supports prompt fields such as system_instructions,
        use_default_system_instructions, and citations_enabled.
        """
        # Lazy import: keeps provider_capabilities (and litellm) out of init order.
        from app.services.provider_capabilities import derive_supports_image_input

        system_instructions = yaml_config.get("system_instructions", "")

        provider = yaml_config.get("provider") or yaml_config.get(
            "litellm_provider", ""
        )
        model_name = yaml_config.get("model_name", "")
        custom_provider = yaml_config.get("custom_provider")
        litellm_params = yaml_config.get("litellm_params") or {}
        base_model = (
            litellm_params.get("base_model")
            if isinstance(litellm_params, dict)
            else None
        )

        # Explicit YAML override wins; otherwise re-derive (the hot-reload file
        # fallback reaches this method without the loader having populated it).
        if "supports_image_input" in yaml_config:
            supports_image_input = bool(yaml_config.get("supports_image_input"))
        else:
            supports_image_input = derive_supports_image_input(
                provider=provider,
                model_name=model_name,
                base_model=base_model,
                custom_provider=custom_provider,
            )

        return cls(
            provider=provider,
            model_name=model_name,
            api_key=yaml_config.get("api_key", ""),
            api_base=yaml_config.get("api_base"),
            custom_provider=custom_provider,
            litellm_params=yaml_config.get("litellm_params"),
            system_instructions=system_instructions if system_instructions else None,
            use_default_system_instructions=yaml_config.get(
                "use_default_system_instructions", True
            ),
            citations_enabled=yaml_config.get("citations_enabled", True),
            config_id=yaml_config.get("id"),
            config_name=yaml_config.get("name"),
            is_auto_mode=False,
            billing_tier=yaml_config.get("billing_tier", "free"),
            is_premium=yaml_config.get("billing_tier", "free") == "premium",
            anonymous_enabled=yaml_config.get("anonymous_enabled", False),
            quota_reserve_tokens=yaml_config.get("quota_reserve_tokens"),
            supports_image_input=supports_image_input,
        )


def load_llm_config_from_yaml(llm_config_id: int = -1) -> dict | None:
    """Load a specific LLM config from global_llm_config.yaml."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    config_file = base_dir / "app" / "config" / "global_llm_config.yaml"

    if not config_file.exists():
        config_file = base_dir / "app" / "config" / "global_llm_config.example.yaml"
        if not config_file.exists():
            print("Error: No global_llm_config.yaml or example file found")
            return None

    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            configs = data.get("global_llm_configs", [])
            for cfg in configs:
                if isinstance(cfg, dict) and cfg.get("id") == llm_config_id:
                    return cfg

            print(f"Error: Global LLM config id {llm_config_id} not found")
            return None
    except Exception as e:
        print(f"Error loading config: {e}")
        return None


def load_global_llm_config_by_id(llm_config_id: int) -> dict | None:
    """Load a global LLM config by ID, checking in-memory configs first.

    In-memory covers both static YAML and dynamically injected configs (e.g.
    OpenRouter integration models that only exist in memory).
    """
    from app.config import config as app_config

    for cfg in app_config.GLOBAL_LLM_CONFIGS:
        if cfg.get("id") == llm_config_id:
            return cfg
    # Fallback to YAML file read (covers hot-reload edge cases).
    return load_llm_config_from_yaml(llm_config_id)


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """Create a ChatLiteLLM instance from a global LLM config dictionary."""
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider") or llm_config.get(
            "litellm_provider", "openai"
        )
        model_string = f"{provider}/{llm_config['model_name']}"

    litellm_kwargs = {
        "model": model_string,
        "api_key": llm_config.get("api_key"),
        "streaming": True,
    }
    if llm_config.get("api_base"):
        litellm_kwargs["api_base"] = llm_config["api_base"]
    if llm_config.get("litellm_params"):
        litellm_kwargs.update(llm_config["litellm_params"])

    llm = SanitizedChatLiteLLM(**litellm_kwargs)
    _attach_model_profile(llm, model_string)
    # agent_config=None: the YAML path lacks structured provider intent, so set
    # only the universal cache_control_injection_points.
    apply_litellm_prompt_caching(llm)
    return llm


def create_chat_litellm_from_agent_config(
    agent_config: AgentConfig,
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Create a ChatLiteLLM from an already resolved concrete model config."""
    if agent_config.is_auto_mode:
        print(
            "Error: Auto mode must be resolved to a concrete model before LLM creation"
        )
        return None

    if agent_config.custom_provider:
        model_string = f"{agent_config.custom_provider}/{agent_config.model_name}"
    else:
        model_string = f"{agent_config.provider}/{agent_config.model_name}"

    litellm_kwargs = {
        "model": model_string,
        "api_key": agent_config.api_key,
        "streaming": True,
    }
    if agent_config.api_base:
        litellm_kwargs["api_base"] = agent_config.api_base
    if agent_config.litellm_params:
        litellm_kwargs.update(agent_config.litellm_params)

    llm = SanitizedChatLiteLLM(**litellm_kwargs)
    _attach_model_profile(llm, model_string)
    # Build-time caching only; the per-thread prompt_cache_key is layered on
    # later in create_surfsense_deep_agent once thread_id is known.
    apply_litellm_prompt_caching(llm, agent_config=agent_config)
    return llm
