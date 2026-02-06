"""
Image Generation Router Service for Load Balancing

This module provides a singleton LiteLLM Router for automatic load balancing
across multiple image generation deployments. It uses litellm.Router which
natively supports aimage_generation() for async image generation.

The router handles:
- Rate limit management with automatic cooldowns
- Automatic failover and retries
- Usage-based routing to distribute load evenly

Supported providers: OpenAI, Azure, Google AI Studio, Vertex AI,
AWS Bedrock, Recraft, OpenRouter, Xinference, Nscale.
"""

import logging
from typing import Any

from litellm import Router
from litellm.utils import ImageResponse

logger = logging.getLogger(__name__)

# Special ID for Auto mode - uses router for load balancing
IMAGE_GEN_AUTO_MODE_ID = 0

# Provider mapping for LiteLLM model string construction.
# Only includes providers that support image generation.
# See: https://docs.litellm.ai/docs/image_generation#supported-providers
IMAGE_GEN_PROVIDER_MAP = {
    "OPENAI": "openai",
    "AZURE_OPENAI": "azure",
    "GOOGLE": "gemini",  # Google AI Studio
    "VERTEX_AI": "vertex_ai",
    "BEDROCK": "bedrock",  # AWS Bedrock
    "RECRAFT": "recraft",
    "OPENROUTER": "openrouter",
    "XINFERENCE": "xinference",
    "NSCALE": "nscale",
}


class ImageGenRouterService:
    """
    Singleton service for managing LiteLLM Router for image generation.

    The router provides automatic load balancing, failover, and rate limit
    handling across multiple image generation deployments.
    Uses Router.aimage_generation() for async image generation calls.
    """

    _instance = None
    _router: Router | None = None
    _model_list: list[dict] = []
    _router_settings: dict = {}
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ImageGenRouterService":
        """Get the singleton instance of the router service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(
        cls,
        global_configs: list[dict],
        router_settings: dict | None = None,
    ) -> None:
        """
        Initialize the router with global image generation configurations.

        Args:
            global_configs: List of global image gen config dictionaries from YAML
            router_settings: Optional router settings (routing_strategy, num_retries, etc.)
        """
        instance = cls.get_instance()

        if instance._initialized:
            logger.debug("Image Generation Router already initialized, skipping")
            return

        # Build model list from global configs
        model_list = []
        for config in global_configs:
            deployment = cls._config_to_deployment(config)
            if deployment:
                model_list.append(deployment)

        if not model_list:
            logger.warning(
                "No valid image generation configs found for router initialization"
            )
            return

        instance._model_list = model_list
        instance._router_settings = router_settings or {}

        # Default router settings optimized for rate limit handling
        default_settings = {
            "routing_strategy": "usage-based-routing",
            "num_retries": 3,
            "allowed_fails": 3,
            "cooldown_time": 60,
            "retry_after": 5,
        }

        # Merge with provided settings
        final_settings = {**default_settings, **instance._router_settings}

        try:
            instance._router = Router(
                model_list=model_list,
                routing_strategy=final_settings.get(
                    "routing_strategy", "usage-based-routing"
                ),
                num_retries=final_settings.get("num_retries", 3),
                allowed_fails=final_settings.get("allowed_fails", 3),
                cooldown_time=final_settings.get("cooldown_time", 60),
                set_verbose=False,
            )
            instance._initialized = True
            logger.info(
                f"Image Generation Router initialized with {len(model_list)} deployments, "
                f"strategy: {final_settings.get('routing_strategy')}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Image Generation Router: {e}")
            instance._router = None

    @classmethod
    def _config_to_deployment(cls, config: dict) -> dict | None:
        """
        Convert a global image gen config to a router deployment entry.

        Args:
            config: Global image gen config dictionary

        Returns:
            Router deployment dictionary or None if invalid
        """
        try:
            # Skip if essential fields are missing
            if not config.get("model_name") or not config.get("api_key"):
                return None

            # Build model string
            if config.get("custom_provider"):
                model_string = f"{config['custom_provider']}/{config['model_name']}"
            else:
                provider = config.get("provider", "").upper()
                provider_prefix = IMAGE_GEN_PROVIDER_MAP.get(provider, provider.lower())
                model_string = f"{provider_prefix}/{config['model_name']}"

            # Build litellm params
            litellm_params: dict[str, Any] = {
                "model": model_string,
                "api_key": config.get("api_key"),
            }

            # Add optional api_base
            if config.get("api_base"):
                litellm_params["api_base"] = config["api_base"]

            # Add api_version (required for Azure)
            if config.get("api_version"):
                litellm_params["api_version"] = config["api_version"]

            # Add any additional litellm parameters
            if config.get("litellm_params"):
                litellm_params.update(config["litellm_params"])

            # All configs use same alias "auto" for unified routing
            deployment: dict[str, Any] = {
                "model_name": "auto",
                "litellm_params": litellm_params,
            }

            # Add RPM rate limit from config if available
            # Note: TPM (tokens per minute) is not applicable for image generation
            # since image APIs are rate-limited by requests, not tokens.
            if config.get("rpm"):
                deployment["rpm"] = config["rpm"]

            return deployment

        except Exception as e:
            logger.warning(f"Failed to convert image gen config to deployment: {e}")
            return None

    @classmethod
    def get_router(cls) -> Router | None:
        """Get the initialized router instance."""
        instance = cls.get_instance()
        return instance._router

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the router has been initialized."""
        instance = cls.get_instance()
        return instance._initialized and instance._router is not None

    @classmethod
    def get_model_count(cls) -> int:
        """Get the number of models in the router."""
        instance = cls.get_instance()
        return len(instance._model_list)

    @classmethod
    async def aimage_generation(
        cls,
        prompt: str,
        model: str = "auto",
        n: int | None = None,
        timeout: int = 600,
        **kwargs,
    ) -> ImageResponse:
        """
        Generate images using the router for load balancing.

        Uses Router.aimage_generation() which distributes requests
        across configured image generation deployments.

        Parameters like size, quality, style, and response_format are intentionally
        omitted to keep the interface model-agnostic. Providers use their own
        sensible defaults. If needed, pass them via **kwargs.

        Args:
            prompt: Text description of the desired image(s)
            model: Model alias (default "auto" for router routing)
            n: Number of images to generate
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific params (size, quality, etc.)

        Returns:
            ImageResponse from litellm

        Raises:
            ValueError: If router is not initialized
        """
        instance = cls.get_instance()
        if not instance._router:
            raise ValueError(
                "Image Generation Router not initialized. "
                "Ensure global_llm_config.yaml has global_image_generation_configs."
            )

        # Build kwargs for aimage_generation
        gen_kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "timeout": timeout,
        }
        if n is not None:
            gen_kwargs["n"] = n
        gen_kwargs.update(kwargs)

        return await instance._router.aimage_generation(**gen_kwargs)


def is_image_gen_auto_mode(config_id: int | None) -> bool:
    """
    Check if the given config ID represents Image Generation Auto mode.

    Args:
        config_id: The config ID to check

    Returns:
        True if this is Auto mode, False otherwise
    """
    return config_id == IMAGE_GEN_AUTO_MODE_ID
