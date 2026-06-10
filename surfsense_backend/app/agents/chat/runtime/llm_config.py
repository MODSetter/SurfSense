"""
LLM configuration utilities for SurfSense agents.

This module provides functions for loading LLM configurations from:
1. Auto mode (ID 0) - Uses LiteLLM Router for load balancing
2. YAML files (global configs with negative IDs)
3. Database NewLLMConfig table (user-created configs with positive IDs)

It also provides utilities for creating ChatLiteLLM instances and
managing prompt configurations.
"""

from collections.abc import AsyncIterator
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.prompt_caching import (
    apply_litellm_prompt_caching,
)
from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    LLMRouterService,
    _sanitize_content,
    get_auto_mode_llm,
    is_auto_mode,
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
    for msg in messages:
        if isinstance(msg.content, list):
            msg.content = _sanitize_content(msg.content)
        if (
            isinstance(msg, AIMessage)
            and (not msg.content or msg.content == "")
            and getattr(msg, "tool_calls", None)
        ):
            msg.content = None  # type: ignore[assignment]
    return messages


class SanitizedChatLiteLLM(ChatLiteLLM):
    """ChatLiteLLM subclass that strips provider-specific content blocks
    (e.g. ``thinking`` from reasoning models) and normalises bare strings
    in content arrays before forwarding to the underlying provider."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return super()._generate(
            _sanitize_messages(messages), stop, run_manager, **kwargs
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        async for chunk in super()._astream(
            _sanitize_messages(messages), stop, run_manager, **kwargs
        ):
            yield chunk


# Re-exported under the historical name ``PROVIDER_MAP``. Source of truth lives
# in provider_capabilities so the YAML loader can resolve prefixes during
# app.config init without importing the agent/tools tree.
from app.services.provider_capabilities import (  # noqa: E402
    _PROVIDER_PREFIX_MAP as PROVIDER_MAP,
)


def _attach_model_profile(llm: ChatLiteLLM, model_string: str) -> None:
    """Attach a ``profile`` dict to ChatLiteLLM with model context metadata."""
    try:
        info = get_model_info(model_string)
        max_input_tokens = info.get("max_input_tokens")
        if isinstance(max_input_tokens, int) and max_input_tokens > 0:
            llm.profile = {
                "max_input_tokens": max_input_tokens,
                "max_input_tokens_upper": max_input_tokens,
                "token_count_model": model_string,
                "token_count_models": [model_string],
            }
    except Exception:
        return


@dataclass
class AgentConfig:
    """
    Complete configuration for the SurfSense agent.

    This combines LLM settings with prompt configuration from NewLLMConfig.
    Supports Auto mode (ID 0) which uses LiteLLM Router for load balancing.
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
            config_name="Auto (Fastest)",
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
    def from_new_llm_config(cls, config) -> "AgentConfig":
        """Build an AgentConfig from a NewLLMConfig database model."""
        # Lazy import: keeps provider_capabilities (and litellm) out of init order.
        from app.services.provider_capabilities import derive_supports_image_input

        provider_value = (
            config.provider.value
            if hasattr(config.provider, "value")
            else str(config.provider)
        )
        litellm_params = config.litellm_params or {}
        base_model = (
            litellm_params.get("base_model")
            if isinstance(litellm_params, dict)
            else None
        )

        return cls(
            provider=provider_value,
            model_name=config.model_name,
            api_key=config.api_key,
            api_base=config.api_base,
            custom_provider=config.custom_provider,
            litellm_params=config.litellm_params,
            system_instructions=config.system_instructions,
            use_default_system_instructions=config.use_default_system_instructions,
            citations_enabled=config.citations_enabled,
            config_id=config.id,
            config_name=config.name,
            is_auto_mode=False,
            billing_tier="free",
            is_premium=False,
            anonymous_enabled=False,
            quota_reserve_tokens=None,
            # BYOK rows have no curated flag; ask LiteLLM (default-allow on
            # unknown). The streaming safety net still blocks explicit text-only.
            supports_image_input=derive_supports_image_input(
                provider=provider_value,
                model_name=config.model_name,
                base_model=base_model,
                custom_provider=config.custom_provider,
            ),
        )

    @classmethod
    def from_yaml_config(cls, yaml_config: dict) -> "AgentConfig":
        """Build an AgentConfig from a YAML configuration dictionary.

        Supports the same prompt fields as NewLLMConfig (system_instructions,
        use_default_system_instructions, citations_enabled).
        """
        # Lazy import: keeps provider_capabilities (and litellm) out of init order.
        from app.services.provider_capabilities import derive_supports_image_input

        system_instructions = yaml_config.get("system_instructions", "")

        provider = yaml_config.get("provider", "").upper()
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


async def load_new_llm_config_from_db(
    session: AsyncSession,
    config_id: int,
) -> "AgentConfig | None":
    """Load a NewLLMConfig from the database by ID."""
    from app.db import NewLLMConfig

    try:
        result = await session.execute(
            select(NewLLMConfig).filter(NewLLMConfig.id == config_id)
        )
        config = result.scalars().first()

        if not config:
            print(f"Error: NewLLMConfig with id {config_id} not found")
            return None

        return AgentConfig.from_new_llm_config(config)
    except Exception as e:
        print(f"Error loading NewLLMConfig from database: {e}")
        return None


async def load_agent_llm_config_for_search_space(
    session: AsyncSession,
    search_space_id: int,
) -> "AgentConfig | None":
    """Load the chat model config for a search space via its agent_llm_id.

    Positive id -> DB; negative -> YAML; None -> first global config (-1).
    """
    from app.db import SearchSpace

    try:
        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            print(f"Error: SearchSpace with id {search_space_id} not found")
            return None

        config_id = (
            search_space.agent_llm_id if search_space.agent_llm_id is not None else -1
        )
        return await load_agent_config(session, config_id, search_space_id)
    except Exception as e:
        print(f"Error loading chat model config for search space {search_space_id}: {e}")
        return None


async def load_agent_config(
    session: AsyncSession,
    config_id: int,
    search_space_id: int | None = None,
) -> "AgentConfig | None":
    """Main config loader: id 0 -> Auto mode; negative -> YAML; positive -> DB."""
    if is_auto_mode(config_id):
        if not LLMRouterService.is_initialized():
            print("Error: Auto mode requested but LLM Router not initialized")
            return None
        return AgentConfig.from_auto_mode()

    if config_id < 0:
        # In-memory covers static YAML + dynamic OpenRouter configs.
        from app.config import config as app_config

        for cfg in app_config.GLOBAL_LLM_CONFIGS:
            if cfg.get("id") == config_id:
                return AgentConfig.from_yaml_config(cfg)
        yaml_config = load_llm_config_from_yaml(config_id)
        if yaml_config:
            return AgentConfig.from_yaml_config(yaml_config)
        return None
    else:
        return await load_new_llm_config_from_db(session, config_id)


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """Create a ChatLiteLLM instance from a global LLM config dictionary."""
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider", "").upper()
        provider_prefix = PROVIDER_MAP.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{llm_config['model_name']}"

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
    """Create a ChatLiteLLM (or, for Auto mode, a load-balancing router) from config."""
    if agent_config.is_auto_mode:
        if not LLMRouterService.is_initialized():
            print("Error: Auto mode requested but LLM Router not initialized")
            return None
        try:
            router_llm = get_auto_mode_llm()
            if router_llm is not None:
                # Universal injection points only: auto-mode fans out across
                # providers, so provider-specific kwargs have no known target.
                apply_litellm_prompt_caching(router_llm, agent_config=agent_config)
            return router_llm
        except Exception as e:
            print(f"Error creating ChatLiteLLMRouter: {e}")
            return None

    if agent_config.custom_provider:
        model_string = f"{agent_config.custom_provider}/{agent_config.model_name}"
    else:
        provider_prefix = PROVIDER_MAP.get(
            agent_config.provider, agent_config.provider.lower()
        )
        model_string = f"{provider_prefix}/{agent_config.model_name}"

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
