"""
LLM configuration utilities for SurfSense agents.

This module provides functions for loading LLM configurations from YAML files
and creating ChatLiteLLM instances from configuration dictionaries.
"""

from pathlib import Path

import yaml
from langchain_litellm import ChatLiteLLM


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


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """
    Create a ChatLiteLLM instance from a global LLM config.

    Args:
        llm_config: LLM configuration dictionary from YAML

    Returns:
        ChatLiteLLM instance or None on error
    """
    # Provider mapping (same as in llm_service.py)
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
        "XAI": "xai",
        "BEDROCK": "bedrock",
        "VERTEX_AI": "vertex_ai",
        "TOGETHER_AI": "together_ai",
        "FIREWORKS_AI": "fireworks_ai",
        "DEEPSEEK": "openai",
        "ALIBABA_QWEN": "openai",
        "MOONSHOT": "openai",
        "ZHIPU": "openai",
    }

    # Build the model string
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider", "").upper()
        provider_prefix = provider_map.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{llm_config['model_name']}"

    # Create ChatLiteLLM instance
    litellm_kwargs = {
        "model": model_string,
        "api_key": llm_config.get("api_key"),
    }

    # Add optional parameters
    if llm_config.get("api_base"):
        litellm_kwargs["api_base"] = llm_config["api_base"]

    # Add any additional litellm parameters
    if llm_config.get("litellm_params"):
        litellm_kwargs.update(llm_config["litellm_params"])

    return ChatLiteLLM(**litellm_kwargs)
