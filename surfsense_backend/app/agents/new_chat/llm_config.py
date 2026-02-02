"""
LLM configuration utilities for SurfSense agents.

This module provides functions for loading LLM configurations from:
1. Auto mode (ID 0) - Uses LiteLLM Router for load balancing
2. YAML files (global configs with negative IDs)
3. Database NewLLMConfig table (user-created configs with positive IDs)

It also provides utilities for creating ChatLiteLLM instances and
managing prompt configurations.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from langchain_litellm import ChatLiteLLM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    LLMRouterService,
    is_auto_mode,
)

# Provider mapping for LiteLLM model string construction
PROVIDER_MAP = {
    "OPENAI": "openai",
    "ANTHROPIC": "anthropic",
    "GROQ": "groq",
    "COHERE": "cohere",
    "GOOGLE": "gemini",
    "OLLAMA": "ollama_chat",
    "MISTRAL": "mistral",
    "AZURE_OPENAI": "azure",
    "OPENROUTER": "openrouter",
    "XAI": "xai",
    "BEDROCK": "bedrock",
    "VERTEX_AI": "vertex_ai",
    "TOGETHER_AI": "together_ai",
    "FIREWORKS_AI": "fireworks_ai",
    "DEEPSEEK": "openai",
    "ALIBABA_QWEN": "openai",
    "MOONSHOT": "openai",
    "ZHIPU": "openai",
    "REPLICATE": "replicate",
    "PERPLEXITY": "perplexity",
    "ANYSCALE": "anyscale",
    "DEEPINFRA": "deepinfra",
    "CEREBRAS": "cerebras",
    "SAMBANOVA": "sambanova",
    "AI21": "ai21",
    "CLOUDFLARE": "cloudflare",
    "DATABRICKS": "databricks",
    "COMETAPI": "cometapi",
    "HUGGINGFACE": "huggingface",
    "CUSTOM": "custom",
}


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
            config_name="Auto (Load Balanced)",
            is_auto_mode=True,
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
        return cls(
            provider=config.provider.value
            if hasattr(config.provider, "value")
            else str(config.provider),
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
        # Get system instructions from YAML, default to empty string
        system_instructions = yaml_config.get("system_instructions", "")

        return cls(
            provider=yaml_config.get("provider", "").upper(),
            model_name=yaml_config.get("model_name", ""),
            api_key=yaml_config.get("api_key", ""),
            api_base=yaml_config.get("api_base"),
            custom_provider=yaml_config.get("custom_provider"),
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
        # Load from YAML (global configs have negative IDs)
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

    return ChatLiteLLM(**litellm_kwargs)


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
            return ChatLiteLLMRouter()
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

    return ChatLiteLLM(**litellm_kwargs)
