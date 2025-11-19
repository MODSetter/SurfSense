import logging
from typing import Any

import litellm
from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import LLMConfig, UserSearchSpacePreference

# Configure litellm to automatically drop unsupported parameters
litellm.drop_params = True

logger = logging.getLogger(__name__)

# Default fallback LLM config ID (Mistral NeMo local)
# Used when primary cloud API fails
FALLBACK_LLM_CONFIG_ID = -1


class ChatLiteLLMWithFallback:
    """
    Wrapper around ChatLiteLLM that provides automatic fallback to another LLM
    when the primary LLM fails (e.g., Ollama memory errors).
    """

    def __init__(self, primary_llm: ChatLiteLLM, fallback_llm: ChatLiteLLM | None = None):
        self.primary_llm = primary_llm
        self.fallback_llm = fallback_llm
        self._using_fallback = False

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    async def ainvoke(self, messages: list, **kwargs) -> Any:
        """Invoke with automatic fallback on failure."""
        try:
            self._using_fallback = False
            return await self.primary_llm.ainvoke(messages, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            # Check for errors that warrant fallback (local or cloud)
            if self.fallback_llm and (
                "memory" in error_str
                or "ollama" in error_str
                or "connection" in error_str
                or "timeout" in error_str
                or "rate" in error_str
                or "quota" in error_str
                or "api" in error_str
                or "503" in error_str
                or "500" in error_str
                or "429" in error_str
            ):
                logger.warning(
                    f"Primary LLM failed with error: {e}. Falling back to secondary LLM."
                )
                self._using_fallback = True
                return await self.fallback_llm.ainvoke(messages, **kwargs)
            raise

    async def astream(self, messages: list, **kwargs):
        """Stream with automatic fallback on failure."""
        try:
            self._using_fallback = False
            async for chunk in self.primary_llm.astream(messages, **kwargs):
                yield chunk
        except Exception as e:
            error_str = str(e).lower()
            if self.fallback_llm and (
                "memory" in error_str
                or "ollama" in error_str
                or "connection" in error_str
                or "timeout" in error_str
                or "rate" in error_str
                or "quota" in error_str
                or "api" in error_str
                or "503" in error_str
                or "500" in error_str
                or "429" in error_str
            ):
                logger.warning(
                    f"Primary LLM streaming failed with error: {e}. Falling back to secondary LLM."
                )
                self._using_fallback = True
                async for chunk in self.fallback_llm.astream(messages, **kwargs):
                    yield chunk
            else:
                raise

    def invoke(self, messages: list, **kwargs) -> Any:
        """Synchronous invoke with automatic fallback on failure."""
        try:
            self._using_fallback = False
            return self.primary_llm.invoke(messages, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if self.fallback_llm and (
                "memory" in error_str
                or "ollama" in error_str
                or "connection" in error_str
                or "timeout" in error_str
                or "rate" in error_str
                or "quota" in error_str
                or "api" in error_str
                or "503" in error_str
                or "500" in error_str
                or "429" in error_str
            ):
                logger.warning(
                    f"Primary LLM failed with error: {e}. Falling back to secondary LLM."
                )
                self._using_fallback = True
                return self.fallback_llm.invoke(messages, **kwargs)
            raise

    def stream(self, messages: list, **kwargs):
        """Synchronous stream with automatic fallback on failure."""
        try:
            self._using_fallback = False
            for chunk in self.primary_llm.stream(messages, **kwargs):
                yield chunk
        except Exception as e:
            error_str = str(e).lower()
            if self.fallback_llm and (
                "memory" in error_str
                or "ollama" in error_str
                or "connection" in error_str
                or "timeout" in error_str
                or "rate" in error_str
                or "quota" in error_str
                or "api" in error_str
                or "503" in error_str
                or "500" in error_str
                or "429" in error_str
            ):
                logger.warning(
                    f"Primary LLM streaming failed with error: {e}. Falling back to secondary LLM."
                )
                self._using_fallback = True
                for chunk in self.fallback_llm.stream(messages, **kwargs):
                    yield chunk
            else:
                raise

    # Proxy other attributes to primary LLM
    def __getattr__(self, name):
        return getattr(self.primary_llm, name)


def _wrap_with_fallback(
    primary_llm: ChatLiteLLM,
    primary_model_name: str,
) -> ChatLiteLLM | ChatLiteLLMWithFallback:
    """
    Wrap an LLM with fallback support if a fallback config is available.

    Args:
        primary_llm: The primary LLM instance
        primary_model_name: Name of the primary model (to prevent circular fallback)

    Returns:
        ChatLiteLLMWithFallback if fallback available, otherwise original LLM
    """
    fallback_config = get_global_llm_config(FALLBACK_LLM_CONFIG_ID)
    if not fallback_config:
        return primary_llm

    # Prevent circular fallback - don't fall back to the same model
    if fallback_config.get("model_name") == primary_model_name:
        logger.warning(
            f"Skipping fallback: primary model '{primary_model_name}' is same as fallback"
        )
        return primary_llm

    fallback_llm = _build_llm_from_global_config(fallback_config)
    fallback_model_name = fallback_config.get("model_name", "unknown")
    logger.info(
        f"Created LLM with fallback: {primary_model_name} -> {fallback_model_name}"
    )
    return ChatLiteLLMWithFallback(primary_llm, fallback_llm)


def _build_llm_from_global_config(global_config: dict) -> ChatLiteLLM:
    """
    Build a ChatLiteLLM instance from a global config dictionary.

    Args:
        global_config: Global LLM config dictionary

    Returns:
        ChatLiteLLM instance

    Raises:
        ValueError: If required configuration keys are missing
    """
    # Validate required keys
    model_name = global_config.get("model_name")
    provider = global_config.get("provider")

    if not model_name:
        raise ValueError("Global LLM config missing required 'model_name' field")
    if not provider:
        raise ValueError("Global LLM config missing required 'provider' field")

    # Build model string
    custom_provider = global_config.get("custom_provider")
    if custom_provider:
        model_string = f"{custom_provider}/{model_name}"
    else:
        provider_map = {
            "OPENAI": "openai",
            "ANTHROPIC": "anthropic",
            "GROQ": "groq",
            "COHERE": "cohere",
            "GOOGLE": "gemini",
            "OLLAMA": "ollama",
            "MISTRAL": "mistral",
            "AZURE_OPENAI": "azure",
            "OPENROUTER": "openrouter",
            "COMETAPI": "cometapi",
            "XAI": "xai",
            "BEDROCK": "bedrock",
            "AWS_BEDROCK": "bedrock",
            "VERTEX_AI": "vertex_ai",
            "TOGETHER_AI": "together_ai",
            "FIREWORKS_AI": "fireworks_ai",
            "REPLICATE": "replicate",
            "PERPLEXITY": "perplexity",
            "ANYSCALE": "anyscale",
            "DEEPINFRA": "deepinfra",
            "CEREBRAS": "cerebras",
            "SAMBANOVA": "sambanova",
            "AI21": "ai21",
            "CLOUDFLARE": "cloudflare",
            "DATABRICKS": "databricks",
            "DEEPSEEK": "openai",
            "ALIBABA_QWEN": "openai",
            "MOONSHOT": "openai",
            "ZHIPU": "openai",
        }
        provider_prefix = provider_map.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{model_name}"

    # Create ChatLiteLLM instance
    litellm_kwargs = {
        "model": model_string,
        "api_key": global_config.get("api_key", ""),
    }

    api_base = global_config.get("api_base")
    if api_base:
        litellm_kwargs["api_base"] = api_base

    litellm_params = global_config.get("litellm_params")
    if litellm_params:
        litellm_kwargs.update(litellm_params)

    return ChatLiteLLM(**litellm_kwargs)


class LLMRole:
    LONG_CONTEXT = "long_context"
    FAST = "fast"
    STRATEGIC = "strategic"


def get_global_llm_config(llm_config_id: int) -> dict | None:
    """
    Get a global LLM configuration by ID.
    Global configs have negative IDs.

    Args:
        llm_config_id: The ID of the global config (should be negative)

    Returns:
        dict: Global config dictionary or None if not found
    """
    if llm_config_id >= 0:
        return None

    for cfg in config.GLOBAL_LLM_CONFIGS:
        if cfg.get("id") == llm_config_id:
            return cfg

    return None


async def validate_llm_config(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str | None = None,
    custom_provider: str | None = None,
    litellm_params: dict | None = None,
) -> tuple[bool, str]:
    """
    Validate an LLM configuration by attempting to make a test API call.

    Args:
        provider: LLM provider (e.g., 'OPENAI', 'ANTHROPIC')
        model_name: Model identifier
        api_key: API key for the provider
        api_base: Optional custom API base URL
        custom_provider: Optional custom provider string
        litellm_params: Optional additional litellm parameters

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if config works, False otherwise
        - error_message: Empty string if valid, error description if invalid
    """
    try:
        # Build the model string for litellm
        if custom_provider:
            model_string = f"{custom_provider}/{model_name}"
        else:
            # Map provider enum to litellm format
            provider_map = {
                "OPENAI": "openai",
                "ANTHROPIC": "anthropic",
                "GROQ": "groq",
                "COHERE": "cohere",
                "GOOGLE": "gemini",
                "OLLAMA": "ollama",
                "MISTRAL": "mistral",
                "AZURE_OPENAI": "azure",
                "OPENROUTER": "openrouter",
                "COMETAPI": "cometapi",
                "XAI": "xai",
                "BEDROCK": "bedrock",
                "AWS_BEDROCK": "bedrock",  # Legacy support (backward compatibility)
                "VERTEX_AI": "vertex_ai",
                "TOGETHER_AI": "together_ai",
                "FIREWORKS_AI": "fireworks_ai",
                "REPLICATE": "replicate",
                "PERPLEXITY": "perplexity",
                "ANYSCALE": "anyscale",
                "DEEPINFRA": "deepinfra",
                "CEREBRAS": "cerebras",
                "SAMBANOVA": "sambanova",
                "AI21": "ai21",
                "CLOUDFLARE": "cloudflare",
                "DATABRICKS": "databricks",
                # Chinese LLM providers
                "DEEPSEEK": "openai",
                "ALIBABA_QWEN": "openai",
                "MOONSHOT": "openai",
                "ZHIPU": "openai",  # GLM needs special handling
            }
            provider_prefix = provider_map.get(provider, provider.lower())
            model_string = f"{provider_prefix}/{model_name}"

        # Create ChatLiteLLM instance
        litellm_kwargs = {
            "model": model_string,
            "api_key": api_key,
            "timeout": 30,  # Set a timeout for validation
        }

        # Add optional parameters
        if api_base:
            litellm_kwargs["api_base"] = api_base

        # Add any additional litellm parameters
        if litellm_params:
            litellm_kwargs.update(litellm_params)

        llm = ChatLiteLLM(**litellm_kwargs)

        # Make a simple test call
        test_message = HumanMessage(content="Hello")
        response = await llm.ainvoke([test_message])

        # If we got here without exception, the config is valid
        if response and response.content:
            logger.info(f"Successfully validated LLM config for model: {model_string}")
            return True, ""
        else:
            logger.warning(
                f"LLM config validation returned empty response for model: {model_string}"
            )
            return False, "LLM returned an empty response"

    except Exception as e:
        error_msg = f"Failed to validate LLM configuration: {e!s}"
        logger.error(error_msg)
        return False, error_msg


async def get_user_llm_instance(
    session: AsyncSession, user_id: str, search_space_id: int, role: str
) -> ChatLiteLLM | ChatLiteLLMWithFallback | None:
    """
    Get a ChatLiteLLM instance for a specific user, search space, and role.
    Automatically wraps with fallback support for local models.

    Args:
        session: Database session
        user_id: User ID
        search_space_id: Search Space ID
        role: LLM role ('long_context', 'fast', or 'strategic')

    Returns:
        ChatLiteLLM or ChatLiteLLMWithFallback instance, or None if not found
    """
    try:
        # Get user's LLM preferences for this search space
        result = await session.execute(
            select(UserSearchSpacePreference).where(
                UserSearchSpacePreference.user_id == user_id,
                UserSearchSpacePreference.search_space_id == search_space_id,
            )
        )
        preference = result.scalars().first()

        if not preference:
            logger.error(
                f"No LLM preferences found for user {user_id} in search space {search_space_id}"
            )
            return None

        # Get the appropriate LLM config ID based on role
        llm_config_id = None
        if role == LLMRole.LONG_CONTEXT:
            llm_config_id = preference.long_context_llm_id
        elif role == LLMRole.FAST:
            llm_config_id = preference.fast_llm_id
        elif role == LLMRole.STRATEGIC:
            llm_config_id = preference.strategic_llm_id
        else:
            logger.error(f"Invalid LLM role: {role}")
            return None

        if not llm_config_id:
            logger.error(
                f"No {role} LLM configured for user {user_id} in search space {search_space_id}"
            )
            return None

        # Check if this is a global config (negative ID)
        if llm_config_id < 0:
            global_config = get_global_llm_config(llm_config_id)
            if not global_config:
                logger.error(f"Global LLM config {llm_config_id} not found")
                return None

            # Build primary LLM from global config
            primary_llm = _build_llm_from_global_config(global_config)

            # Add fallback support for resilience (skip if this IS the fallback config)
            if llm_config_id == FALLBACK_LLM_CONFIG_ID:
                return primary_llm

            return _wrap_with_fallback(primary_llm, global_config["model_name"])

        # Get the LLM configuration from database (user-specific config)
        result = await session.execute(
            select(LLMConfig).where(
                LLMConfig.id == llm_config_id,
                LLMConfig.search_space_id == search_space_id,
            )
        )
        llm_config = result.scalars().first()

        if not llm_config:
            logger.error(
                f"LLM config {llm_config_id} not found in search space {search_space_id}"
            )
            return None

        # Build the model string for litellm / 构建 LiteLLM 的模型字符串
        if llm_config.custom_provider:
            model_string = f"{llm_config.custom_provider}/{llm_config.model_name}"
        else:
            # Map provider enum to litellm format / 将提供商枚举映射为 LiteLLM 格式
            provider_map = {
                "OPENAI": "openai",
                "ANTHROPIC": "anthropic",
                "GROQ": "groq",
                "COHERE": "cohere",
                "GOOGLE": "gemini",
                "OLLAMA": "ollama",
                "MISTRAL": "mistral",
                "AZURE_OPENAI": "azure",
                "OPENROUTER": "openrouter",
                "COMETAPI": "cometapi",
                "XAI": "xai",
                "BEDROCK": "bedrock",
                "AWS_BEDROCK": "bedrock",  # Legacy support (backward compatibility)
                "VERTEX_AI": "vertex_ai",
                "TOGETHER_AI": "together_ai",
                "FIREWORKS_AI": "fireworks_ai",
                "REPLICATE": "replicate",
                "PERPLEXITY": "perplexity",
                "ANYSCALE": "anyscale",
                "DEEPINFRA": "deepinfra",
                "CEREBRAS": "cerebras",
                "SAMBANOVA": "sambanova",
                "AI21": "ai21",
                "CLOUDFLARE": "cloudflare",
                "DATABRICKS": "databricks",
                # Chinese LLM providers
                "DEEPSEEK": "openai",
                "ALIBABA_QWEN": "openai",
                "MOONSHOT": "openai",
                "ZHIPU": "openai",
            }
            provider_prefix = provider_map.get(
                llm_config.provider.value, llm_config.provider.value.lower()
            )
            model_string = f"{provider_prefix}/{llm_config.model_name}"

        # Create ChatLiteLLM instance
        litellm_kwargs = {
            "model": model_string,
            "api_key": llm_config.api_key,
        }

        # Add optional parameters
        if llm_config.api_base:
            litellm_kwargs["api_base"] = llm_config.api_base

        # Add any additional litellm parameters
        if llm_config.litellm_params:
            litellm_kwargs.update(llm_config.litellm_params)

        primary_llm = ChatLiteLLM(**litellm_kwargs)

        # Add fallback support for user-specific configs too
        return _wrap_with_fallback(primary_llm, llm_config.model_name)

    except Exception as e:
        logger.error(
            f"Error getting LLM instance for user {user_id}, role {role}: {e!s}"
        )
        return None


async def get_user_long_context_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Get user's long context LLM instance for a specific search space."""
    return await get_user_llm_instance(
        session, user_id, search_space_id, LLMRole.LONG_CONTEXT
    )


async def get_user_fast_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Get user's fast LLM instance for a specific search space."""
    return await get_user_llm_instance(session, user_id, search_space_id, LLMRole.FAST)


async def get_user_strategic_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Get user's strategic LLM instance for a specific search space."""
    return await get_user_llm_instance(
        session, user_id, search_space_id, LLMRole.STRATEGIC
    )
