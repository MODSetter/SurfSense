from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langchain_community.chat_models import ChatLiteLLM
import logging

from app.db import User, LLMConfig

logger = logging.getLogger(__name__)

class LLMRole:
    LONG_CONTEXT = "long_context"
    FAST = "fast"
    STRATEGIC = "strategic"

async def get_user_llm_instance(
    session: AsyncSession, 
    user_id: str, 
    role: str
) -> Optional[ChatLiteLLM]:
    """
    Get a ChatLiteLLM instance for a specific user and role.
    
    Args:
        session: Database session
        user_id: User ID
        role: LLM role ('long_context', 'fast', or 'strategic')
        
    Returns:
        ChatLiteLLM instance or None if not found
    """
    try:
        # Get user with their LLM preferences
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            logger.error(f"User {user_id} not found")
            return None
        
        # Get the appropriate LLM config ID based on role
        llm_config_id = None
        if role == LLMRole.LONG_CONTEXT:
            llm_config_id = user.long_context_llm_id
        elif role == LLMRole.FAST:
            llm_config_id = user.fast_llm_id
        elif role == LLMRole.STRATEGIC:
            llm_config_id = user.strategic_llm_id
        else:
            logger.error(f"Invalid LLM role: {role}")
            return None
        
        if not llm_config_id:
            logger.error(f"No {role} LLM configured for user {user_id}")
            return None
        
        # Get the LLM configuration
        result = await session.execute(
            select(LLMConfig).where(
                LLMConfig.id == llm_config_id,
                LLMConfig.user_id == user_id
            )
        )
        llm_config = result.scalars().first()
        
        if not llm_config:
            logger.error(f"LLM config {llm_config_id} not found for user {user_id}")
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
                "OLLAMA": "ollama",
                "MISTRAL": "mistral",
                # Add more mappings as needed
            }
            provider_prefix = provider_map.get(llm_config.provider.value, llm_config.provider.value.lower())
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
        logger.error(f"Error getting LLM instance for user {user_id}, role {role}: {str(e)}")
        return None

async def get_user_long_context_llm(session: AsyncSession, user_id: str) -> Optional[ChatLiteLLM]:
    """Get user's long context LLM instance."""
    return await get_user_llm_instance(session, user_id, LLMRole.LONG_CONTEXT)

async def get_user_fast_llm(session: AsyncSession, user_id: str) -> Optional[ChatLiteLLM]:
    """Get user's fast LLM instance."""
    return await get_user_llm_instance(session, user_id, LLMRole.FAST)

async def get_user_strategic_llm(session: AsyncSession, user_id: str) -> Optional[ChatLiteLLM]:
    """Get user's strategic LLM instance."""
    return await get_user_llm_instance(session, user_id, LLMRole.STRATEGIC) 