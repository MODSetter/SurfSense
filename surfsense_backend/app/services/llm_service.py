import logging

import litellm
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import LLMConfig, UserSearchSpacePreference

# Configure litellm to automatically drop unsupported parameters
litellm.drop_params = True

logger = logging.getLogger(__name__)


class LLMRole:
    LONG_CONTEXT = "long_context"
    FAST = "fast"
    STRATEGIC = "strategic"


async def get_user_llm_instance(
    session: AsyncSession, user_id: str, search_space_id: int, role: str
) -> ChatLiteLLM | None:
    """
    Get a ChatLiteLLM instance for a specific user, search space, and role.

    Args:
        session: Database session
        user_id: User ID
        search_space_id: Search Space ID
        role: LLM role ('long_context', 'fast', or 'strategic')

    Returns:
        ChatLiteLLM instance or None if not found
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

        # Get the LLM configuration
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
                # Chinese LLM providers (OpenAI-compatible)
                "DEEPSEEK": "openai",  # DeepSeek uses OpenAI-compatible API
                "ALIBABA_QWEN": "openai",  # Qwen uses OpenAI-compatible API
                "MOONSHOT": "openai",  # Moonshot (Kimi) uses OpenAI-compatible API
                "ZHIPU": "openai",  # Zhipu (GLM) uses OpenAI-compatible API
                # Add more mappings as needed
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
