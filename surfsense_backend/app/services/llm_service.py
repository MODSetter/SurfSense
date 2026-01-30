import logging

import litellm
from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import NewLLMConfig, SearchSpace
from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    LLMRouterService,
    is_auto_mode,
)

# Configure litellm to automatically drop unsupported parameters
litellm.drop_params = True

logger = logging.getLogger(__name__)


class LLMRole:
    AGENT = "agent"  # For agent/chat operations
    DOCUMENT_SUMMARY = "document_summary"  # For document summarization


def get_global_llm_config(llm_config_id: int) -> dict | None:
    """
    Get a global LLM configuration by ID.
    Global configs have negative IDs. ID 0 is reserved for Auto mode.

    Args:
        llm_config_id: The ID of the global config (should be negative or 0 for Auto)

    Returns:
        dict: Global config dictionary or None if not found
    """
    # Auto mode (ID 0) is handled separately via the router
    if llm_config_id == AUTO_MODE_ID:
        return {
            "id": AUTO_MODE_ID,
            "name": "Auto (Load Balanced)",
            "description": "Automatically routes requests across available LLM providers for optimal performance and rate limit handling",
            "provider": "AUTO",
            "model_name": "auto",
            "is_auto_mode": True,
        }

    if llm_config_id > 0:
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
                "OLLAMA": "ollama_chat",
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
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """
    Get a ChatLiteLLM instance for a specific search space and role.

    LLM preferences are stored at the search space level and shared by all members.

    If Auto mode (ID 0) is configured, returns a ChatLiteLLMRouter that uses
    LiteLLM Router for automatic load balancing across available providers.

    Args:
        session: Database session
        search_space_id: Search Space ID
        role: LLM role ('agent' or 'document_summary')

    Returns:
        ChatLiteLLM or ChatLiteLLMRouter instance, or None if not found
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
        if role == LLMRole.AGENT:
            llm_config_id = search_space.agent_llm_id
        elif role == LLMRole.DOCUMENT_SUMMARY:
            llm_config_id = search_space.document_summary_llm_id
        else:
            logger.error(f"Invalid LLM role: {role}")
            return None

        if llm_config_id is None:
            logger.error(f"No {role} LLM configured for search space {search_space_id}")
            return None

        # Check for Auto mode (ID 0) - use router for load balancing
        if is_auto_mode(llm_config_id):
            if not LLMRouterService.is_initialized():
                logger.error(
                    "Auto mode requested but LLM Router not initialized. "
                    "Ensure global_llm_config.yaml exists with valid configs."
                )
                return None

            try:
                logger.debug(
                    f"Using Auto mode (LLM Router) for search space {search_space_id}, role {role}"
                )
                return ChatLiteLLMRouter()
            except Exception as e:
                logger.error(f"Failed to create ChatLiteLLMRouter: {e}")
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
                    "OLLAMA": "ollama_chat",
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

        # Get the LLM configuration from database (NewLLMConfig)
        result = await session.execute(
            select(NewLLMConfig).where(
                NewLLMConfig.id == llm_config_id,
                NewLLMConfig.search_space_id == search_space_id,
            )
        )
        llm_config = result.scalars().first()

        if not llm_config:
            logger.error(
                f"LLM config {llm_config_id} not found in search space {search_space_id}"
            )
            return None

        # Build the model string for litellm
        if llm_config.custom_provider:
            model_string = f"{llm_config.custom_provider}/{llm_config.model_name}"
        else:
            # Map provider enum to litellm format
            provider_map = {
                "OPENAI": "openai",
                "ANTHROPIC": "anthropic",
                "GROQ": "groq",
                "COHERE": "cohere",
                "GOOGLE": "gemini",
                "OLLAMA": "ollama_chat",
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


async def get_agent_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's agent LLM instance for chat operations."""
    return await get_search_space_llm_instance(session, search_space_id, LLMRole.AGENT)


async def get_document_summary_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's document summary LLM instance."""
    return await get_search_space_llm_instance(
        session, search_space_id, LLMRole.DOCUMENT_SUMMARY
    )


# Backward-compatible alias (LLM preferences are now per-search-space, not per-user)
async def get_user_long_context_llm(
    session: AsyncSession, user_id: str, search_space_id: int
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """
    Deprecated: Use get_document_summary_llm instead.
    The user_id parameter is ignored as LLM preferences are now per-search-space.
    """
    return await get_document_summary_llm(session, search_space_id)
