import logging

import litellm
from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import LLMConfig, SearchSpace

# Configure litellm to automatically drop unsupported parameters
litellm.drop_params = True

logger = logging.getLogger(__name__)


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


async def get_search_space_llm_instance(
    session: AsyncSession, search_space_id: int, role: str
) -> ChatLiteLLM | None:
    """
    Get a ChatLiteLLM instance for a specific search space and role.

    LLM preferences are stored at the search space level and shared by all members.

    Args:
        session: Database session
        search_space_id: Search Space ID
        role: LLM role ('long_context', 'fast', or 'strategic')

    Returns:
        ChatLiteLLM instance or None if not found
    """
    try:
        # Get the search space with its LLM preferences
        result = await session.execute(
            select(SearchSpace).where(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            logger.error(f"Search space {search_space_id} not found")
            return None

        # Get the appropriate LLM config ID based on role
        llm_config_id = None
        if role == LLMRole.LONG_CONTEXT:
            llm_config_id = search_space.long_context_llm_id
        elif role == LLMRole.FAST:
            llm_config_id = search_space.fast_llm_id
        elif role == LLMRole.STRATEGIC:
            llm_config_id = search_space.strategic_llm_id
        else:
            logger.error(f"Invalid LLM role: {role}")
            return None

        if not llm_config_id:
            logger.error(f"No {role} LLM configured for search space {search_space_id}")
            return None

        # Check if this is a global config (negative ID)
        if llm_config_id < 0:
            global_config = get_global_llm_config(llm_config_id)
            if not global_config:
                logger.error(f"Global LLM config {llm_config_id} not found")
                return None

            # Build model string for global config
            if global_config.get("custom_provider"):
                model_string = (
                    f"{global_config['custom_provider']}/{global_config['model_name']}"
                )
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
                provider_prefix = provider_map.get(
                    global_config["provider"], global_config["provider"].lower()
                )
                model_string = f"{provider_prefix}/{global_config['model_name']}"

            # Create ChatLiteLLM instance from global config
            litellm_kwargs = {
                "model": model_string,
                "api_key": global_config["api_key"],
            }

            if global_config.get("api_base"):
                litellm_kwargs["api_base"] = global_config["api_base"]

            if global_config.get("litellm_params"):
                litellm_kwargs.update(global_config["litellm_params"])

            return ChatLiteLLM(**litellm_kwargs)

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

        return ChatLiteLLM(**litellm_kwargs)

    except Exception as e:
        logger.error(
            f"Error getting LLM instance for search space {search_space_id}, role {role}: {e!s}"
        )
        return None


async def get_long_context_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | None:
    """Get the search space's long context LLM instance."""
    return await get_search_space_llm_instance(
        session, search_space_id, LLMRole.LONG_CONTEXT
    )


async def get_fast_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | None:
    """Get the search space's fast LLM instance."""
    return await get_search_space_llm_instance(session, search_space_id, LLMRole.FAST)


async def get_strategic_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | None:
    """Get the search space's strategic LLM instance."""
    return await get_search_space_llm_instance(
        session, search_space_id, LLMRole.STRATEGIC
    )


# Backward-compatible aliases (deprecated - will be removed in future versions)
async def get_user_llm_instance(
    session: AsyncSession, user_id: str, search_space_id: int, role: str
) -> ChatLiteLLM | None:
    """
    Deprecated: Use get_search_space_llm_instance instead.
    LLM preferences are now stored at the search space level, not per-user.
    """
    return await get_search_space_llm_instance(session, search_space_id, role)


async def get_user_long_context_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Deprecated: Use get_long_context_llm instead."""
    return await get_long_context_llm(session, search_space_id)


async def get_user_fast_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Deprecated: Use get_fast_llm instead."""
    return await get_fast_llm(session, search_space_id)


async def get_user_strategic_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | None:
    """Deprecated: Use get_strategic_llm instead."""
    return await get_strategic_llm(session, search_space_id)
