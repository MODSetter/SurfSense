"""
LLM configuration utilities for SurfSense agents.

This module provides functions for loading LLM configurations from:
1. Auto mode (ID 0) - Uses LiteLLM Router for load balancing
2. YAML files (global configs with negative IDs)
3. Database NewLLMConfig table (user-created configs with positive IDs)

It also provides utilities for creating ChatLiteLLM instances and
managing prompt configurations.
"""

import copy
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

from app.agents.new_chat.prompt_caching import apply_litellm_prompt_caching
from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    LLMRouterService,
    _sanitize_content,
    get_auto_mode_llm,
    is_auto_mode,
)

# Keys we must echo back from ``AIMessage.additional_kwargs`` into the dict
# sent to the provider on Turn 2. langchain-litellm's
# ``_convert_message_to_dict`` only forwards ``function_call`` / ``tool_calls``
# / ``name``; anything else (DeepSeek's ``reasoning_content``, etc.) is
# silently dropped, which causes DeepSeek's thinking-mode requirement
# ("the reasoning_content in the thinking mode must be passed back to the
# API") to fail on every multi-turn request after a tool call.
_REASONING_PASSTHROUGH_KWARGS: frozenset[str] = frozenset({"reasoning_content"})


def _extract_reasoning_content_from_blocks(content: Any) -> str | None:
    """Recover the reasoning string from a ``content`` list of blocks.

    langchain-litellm's streaming path stores reasoning both in
    ``additional_kwargs["reasoning_content"]`` and as a
    ``{"type": "thinking", "thinking": "<text>"}`` block in ``content``
    (see ``_inject_reasoning_content_into_content``). State persistence /
    serialization can drop ``additional_kwargs``; the content blocks are
    more durable. This helper rebuilds the reasoning string from those
    blocks so the API echo (see :class:`SanitizedChatLiteLLM`) survives a
    round-trip through LangGraph state.
    """
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "thinking":
            text = block.get("thinking")
            if isinstance(text, str) and text:
                parts.append(text)
        elif block_type == "redacted_thinking":
            # Redacted blocks contain opaque base64; surfacing them verbatim
            # preserves DeepSeek's API contract without leaking content
            # we can't render.
            text = block.get("data")
            if isinstance(text, str) and text:
                parts.append(text)
    return "".join(parts) if parts else None


def _sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Sanitize content on every message so it is safe for any provider.

    Handles three cross-provider incompatibilities:
    - List content with provider-specific blocks (e.g. ``thinking``)
    - List content with bare strings or empty text blocks
    - AI messages with empty content + tool calls: some providers (Bedrock)
      convert ``""`` to ``[{"type":"text","text":""}]`` server-side then
      reject the blank text.  The OpenAI spec says ``content`` should be
      ``null`` when an assistant message only carries tool calls.

    The input messages are not mutated. LangGraph state typically holds
    the same ``BaseMessage`` instances we receive here; mutating
    ``msg.content`` in place would corrupt state for any subsequent code
    path (notably reasoning-content recovery on the next turn — see
    :func:`_extract_reasoning_content_from_blocks`).
    """
    sanitized: list[BaseMessage] = []
    for msg in messages:
        new_msg = copy.copy(msg)
        new_content = msg.content
        if isinstance(new_content, list):
            new_content = _sanitize_content(new_content)
        if (
            isinstance(new_msg, AIMessage)
            and (not new_content or new_content == "")
            and getattr(msg, "tool_calls", None)
        ):
            new_content = None  # type: ignore[assignment]
        new_msg.content = new_content
        sanitized.append(new_msg)
    return sanitized


def _attach_reasoning_passthrough(
    original_messages: list[BaseMessage], message_dicts: list[dict[str, Any]]
) -> None:
    """Copy reasoning-passthrough fields from each AIMessage onto the dict
    that langchain-litellm built for the provider request.

    langchain-litellm's ``_convert_message_to_dict`` keeps only a fixed
    set of ``additional_kwargs`` keys (``function_call`` / ``tool_calls``
    / ``name``). Any reasoning field a provider requires us to echo on
    Turn 2 (DeepSeek's ``reasoning_content`` is the canonical case) gets
    silently dropped. This restores the field at the boundary —
    provider-agnostic, no-op when the field is absent.

    If ``additional_kwargs[<key>]`` is missing but the AIMessage's
    ``content`` carries a ``thinking`` block (langchain-litellm's
    streaming path stores reasoning in BOTH places — see
    ``_inject_reasoning_content_into_content``), we recover it from
    there. State persistence layers occasionally retain content blocks
    while losing ``additional_kwargs``; this fallback keeps the echo
    working across that gap.
    """
    if len(original_messages) != len(message_dicts):
        return
    for msg, msg_dict in zip(original_messages, message_dicts, strict=False):
        if not isinstance(msg, AIMessage):
            continue
        extra = getattr(msg, "additional_kwargs", None) or {}
        for key in _REASONING_PASSTHROUGH_KWARGS:
            value = extra.get(key) if isinstance(extra, dict) else None
            if not value and key == "reasoning_content":
                value = _extract_reasoning_content_from_blocks(msg.content)
            if value:
                msg_dict[key] = value


class SanitizedChatLiteLLM(ChatLiteLLM):
    """ChatLiteLLM subclass that strips provider-specific content blocks
    (e.g. ``thinking`` from reasoning models) and normalises bare strings
    in content arrays before forwarding to the underlying provider.

    Also restores ``reasoning_content`` (and any other key in
    :data:`_REASONING_PASSTHROUGH_KWARGS`) onto outgoing message dicts
    after langchain-litellm's ``_convert_message_to_dict`` drops it.
    DeepSeek's thinking-mode contract — "The reasoning_content in the
    thinking mode must be passed back to the API" — fails without this
    on Turn 2 of any tool-calling conversation.
    """

    def _create_message_dicts(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        sanitized = _sanitize_messages(messages)
        message_dicts, params = super()._create_message_dicts(sanitized, stop)
        # Pass the ORIGINAL messages (not sanitized) to the reasoning
        # passthrough — sanitization strips ``thinking`` blocks from
        # ``content``, which is the fallback we rely on when
        # ``additional_kwargs["reasoning_content"]`` is absent. The two
        # lists have the same length (one ``message_dict`` per message)
        # and the same order, so the zip in
        # :func:`_attach_reasoning_passthrough` lines up.
        _attach_reasoning_passthrough(messages, message_dicts)
        return message_dicts, params

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # ``_generate`` does not call ``_create_message_dicts`` directly in
        # all langchain-litellm releases, so sanitize at the boundary too;
        # passthrough still lands via the ``_create_message_dicts`` override
        # invoked downstream.
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


# Provider mapping for LiteLLM model string construction.
#
# Single source of truth lives in
# :mod:`app.services.provider_capabilities` so the YAML loader (which
# runs during ``app.config`` class-body init) can resolve provider
# prefixes without dragging the agent / tools tree into module load
# order. Re-exported here under the historical ``PROVIDER_MAP`` name
# so existing callers (``llm_router_service``, ``image_gen_router_service``,
# tests) keep working unchanged.
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

    # Capability flag: best-effort True for the chat selector / catalog.
    # Resolved via :func:`provider_capabilities.derive_supports_image_input`
    # which prefers OpenRouter's ``architecture.input_modalities`` and
    # otherwise consults LiteLLM's authoritative model map. Default True
    # is the conservative-allow stance — the streaming-task safety net
    # (``is_known_text_only_chat_model``) is the *only* place a False
    # actually blocks a request. Setting this to False here without an
    # authoritative source would silently hide vision-capable models
    # (the regression we're fixing).
    supports_image_input: bool = True

    @classmethod
    def from_auto_mode(cls) -> "AgentConfig":
        """
        Create an AgentConfig for Auto mode (LiteLLM Router load balancing).

        Returns:
            AgentConfig instance configured for Auto mode
        """
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
            # Auto routes across the configured pool, which usually
            # contains at least one vision-capable deployment; the router
            # will surface a 404 from a non-vision deployment as a normal
            # ``allowed_fails`` event and fail over rather than blocking
            # the request outright.
            supports_image_input=True,
        )

    @classmethod
    def from_new_llm_config(cls, config) -> "AgentConfig":
        """
        Create an AgentConfig from a NewLLMConfig database model.

        Args:
            config: NewLLMConfig database model instance

        Returns:
            AgentConfig instance
        """
        # Lazy import to avoid pulling provider_capabilities (and its
        # transitive litellm import) into module-init order.
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
            # BYOK rows have no operator-curated capability flag, so we
            # ask LiteLLM (default-allow on unknown). The streaming
            # safety net still blocks if the model is *explicitly*
            # marked text-only.
            supports_image_input=derive_supports_image_input(
                provider=provider_value,
                model_name=config.model_name,
                base_model=base_model,
                custom_provider=config.custom_provider,
            ),
        )

    @classmethod
    def from_yaml_config(cls, yaml_config: dict) -> "AgentConfig":
        """
        Create an AgentConfig from a YAML configuration dictionary.

        YAML configs now support the same prompt configuration fields as NewLLMConfig:
        - system_instructions: Custom system instructions (empty string uses defaults)
        - use_default_system_instructions: Whether to use default instructions
        - citations_enabled: Whether citations are enabled

        Args:
            yaml_config: Configuration dictionary from YAML file

        Returns:
            AgentConfig instance
        """
        # Lazy import to avoid pulling provider_capabilities (and its
        # transitive litellm import) into module-init order.
        from app.services.provider_capabilities import derive_supports_image_input

        # Get system instructions from YAML, default to empty string
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

        # Explicit YAML override wins; otherwise derive from LiteLLM /
        # OpenRouter modalities. The YAML loader already populates this
        # field, but this method is also called from
        # ``load_global_llm_config_by_id``'s file fallback (hot reload),
        # so we re-derive here for safety. The bool() coercion preserves
        # the loader's behaviour for explicit ``true`` / ``false``
        # strings that PyYAML may surface.
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
            # Prompt configuration from YAML (with defaults for backwards compatibility)
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
    """
    Load a specific LLM config from global_llm_config.yaml.

    Args:
        llm_config_id: The id of the config to load (default: -1)

    Returns:
        LLM config dict or None if not found
    """
    # Get the config file path
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    config_file = base_dir / "app" / "config" / "global_llm_config.yaml"

    # Fallback to example file if main config doesn't exist
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
    """
    Load a global LLM config by ID, checking in-memory configs first.

    This handles both static YAML configs and dynamically injected configs
    (e.g. OpenRouter integration models that only exist in memory).

    Args:
        llm_config_id: The negative ID of the global config to load

    Returns:
        LLM config dict or None if not found
    """
    from app.config import config as app_config

    for cfg in app_config.GLOBAL_LLM_CONFIGS:
        if cfg.get("id") == llm_config_id:
            return cfg
    # Fallback to YAML file read (covers edge cases like hot-reload)
    return load_llm_config_from_yaml(llm_config_id)


async def load_new_llm_config_from_db(
    session: AsyncSession,
    config_id: int,
) -> "AgentConfig | None":
    """
    Load a NewLLMConfig from the database by ID.

    Args:
        session: AsyncSession for database access
        config_id: The ID of the NewLLMConfig to load

    Returns:
        AgentConfig instance or None if not found
    """
    # Import here to avoid circular imports
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
    """
    Load the agent LLM configuration for a search space.

    This loads the LLM config based on the search space's agent_llm_id setting:
    - Positive ID: Load from NewLLMConfig database table
    - Negative ID: Load from YAML global configs
    - None: Falls back to first global config (id=-1)

    Args:
        session: AsyncSession for database access
        search_space_id: The search space ID

    Returns:
        AgentConfig instance or None if not found
    """
    # Import here to avoid circular imports
    from app.db import SearchSpace

    try:
        # Get the search space to check its agent_llm_id preference
        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            print(f"Error: SearchSpace with id {search_space_id} not found")
            return None

        # Use agent_llm_id from search space, fallback to -1 (first global config)
        config_id = (
            search_space.agent_llm_id if search_space.agent_llm_id is not None else -1
        )

        # Load the config using the unified loader
        return await load_agent_config(session, config_id, search_space_id)
    except Exception as e:
        print(f"Error loading agent LLM config for search space {search_space_id}: {e}")
        return None


async def load_agent_config(
    session: AsyncSession,
    config_id: int,
    search_space_id: int | None = None,
) -> "AgentConfig | None":
    """
    Load an agent configuration, supporting Auto mode, YAML, and database configs.

    This is the main entry point for loading configurations:
    - ID 0: Auto mode (uses LiteLLM Router for load balancing)
    - Negative IDs: Load from YAML file (global configs)
    - Positive IDs: Load from NewLLMConfig database table

    Args:
        session: AsyncSession for database access
        config_id: The config ID (0 for Auto, negative for YAML, positive for database)
        search_space_id: Optional search space ID for context

    Returns:
        AgentConfig instance or None if not found
    """
    # Auto mode (ID 0) - use LiteLLM Router
    if is_auto_mode(config_id):
        if not LLMRouterService.is_initialized():
            print("Error: Auto mode requested but LLM Router not initialized")
            return None
        return AgentConfig.from_auto_mode()

    if config_id < 0:
        # Check in-memory configs first (includes static YAML + dynamic OpenRouter)
        from app.config import config as app_config

        for cfg in app_config.GLOBAL_LLM_CONFIGS:
            if cfg.get("id") == config_id:
                return AgentConfig.from_yaml_config(cfg)
        # Fallback to YAML file read for safety
        yaml_config = load_llm_config_from_yaml(config_id)
        if yaml_config:
            return AgentConfig.from_yaml_config(yaml_config)
        return None
    else:
        # Load from database (NewLLMConfig)
        return await load_new_llm_config_from_db(session, config_id)


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """
    Create a ChatLiteLLM instance from a global LLM config dictionary.

    Args:
        llm_config: LLM configuration dictionary from YAML

    Returns:
        ChatLiteLLM instance or None on error
    """
    # Build the model string
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider", "").upper()
        provider_prefix = PROVIDER_MAP.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{llm_config['model_name']}"

    # Create ChatLiteLLM instance with streaming enabled
    litellm_kwargs = {
        "model": model_string,
        "api_key": llm_config.get("api_key"),
        "streaming": True,  # Enable streaming for real-time token streaming
    }

    # Add optional parameters
    if llm_config.get("api_base"):
        litellm_kwargs["api_base"] = llm_config["api_base"]

    # Add any additional litellm parameters
    if llm_config.get("litellm_params"):
        litellm_kwargs.update(llm_config["litellm_params"])

    llm = SanitizedChatLiteLLM(**litellm_kwargs)
    _attach_model_profile(llm, model_string)
    # Configure LiteLLM-native prompt caching (cache_control_injection_points
    # for Anthropic/Bedrock/Vertex/Gemini/Azure-AI/OpenRouter/Databricks/etc.).
    # ``agent_config=None`` here — the YAML path doesn't have provider intent
    # in a structured form, so we set only the universal injection points.
    apply_litellm_prompt_caching(llm)
    return llm


def create_chat_litellm_from_agent_config(
    agent_config: AgentConfig,
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """
    Create a ChatLiteLLM or ChatLiteLLMRouter instance from an AgentConfig.

    For Auto mode configs, returns a ChatLiteLLMRouter that uses LiteLLM Router
    for automatic load balancing across available providers.

    Args:
        agent_config: AgentConfig instance

    Returns:
        ChatLiteLLM or ChatLiteLLMRouter instance, or None on error
    """
    # Handle Auto mode - return ChatLiteLLMRouter
    if agent_config.is_auto_mode:
        if not LLMRouterService.is_initialized():
            print("Error: Auto mode requested but LLM Router not initialized")
            return None
        try:
            router_llm = get_auto_mode_llm()
            if router_llm is not None:
                # Universal cache_control_injection_points only — auto-mode
                # fans out across providers, so OpenAI-only kwargs (e.g.
                # ``prompt_cache_key``) are left off here. ``drop_params``
                # would strip them at the provider boundary anyway, but
                # there's no point setting them when we don't know the
                # destination.
                apply_litellm_prompt_caching(router_llm, agent_config=agent_config)
            return router_llm
        except Exception as e:
            print(f"Error creating ChatLiteLLMRouter: {e}")
            return None

    # Build the model string
    if agent_config.custom_provider:
        model_string = f"{agent_config.custom_provider}/{agent_config.model_name}"
    else:
        provider_prefix = PROVIDER_MAP.get(
            agent_config.provider, agent_config.provider.lower()
        )
        model_string = f"{provider_prefix}/{agent_config.model_name}"

    # Create ChatLiteLLM instance with streaming enabled
    litellm_kwargs = {
        "model": model_string,
        "api_key": agent_config.api_key,
        "streaming": True,  # Enable streaming for real-time token streaming
    }

    # Add optional parameters
    if agent_config.api_base:
        litellm_kwargs["api_base"] = agent_config.api_base

    # Add any additional litellm parameters
    if agent_config.litellm_params:
        litellm_kwargs.update(agent_config.litellm_params)

    llm = SanitizedChatLiteLLM(**litellm_kwargs)
    _attach_model_profile(llm, model_string)
    # Build-time prompt caching: sets ``cache_control_injection_points`` for
    # all providers and (for OpenAI/DeepSeek/xAI) ``prompt_cache_retention``.
    # Per-thread ``prompt_cache_key`` is layered on later in
    # ``create_surfsense_deep_agent`` once ``thread_id`` is known.
    apply_litellm_prompt_caching(llm, agent_config=agent_config)
    return llm
