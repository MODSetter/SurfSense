import logging
from typing import Any

from litellm import Router

from app.services.provider_api_base import resolve_api_base

logger = logging.getLogger(__name__)

VISION_AUTO_MODE_ID = 0

VISION_PROVIDER_MAP = {
    "OPENAI": "openai",
    "ANTHROPIC": "anthropic",
    "GOOGLE": "gemini",
    "AZURE_OPENAI": "azure",
    "VERTEX_AI": "vertex_ai",
    "BEDROCK": "bedrock",
    "XAI": "xai",
    "OPENROUTER": "openrouter",
    "OLLAMA": "ollama_chat",
    "GROQ": "groq",
    "TOGETHER_AI": "together_ai",
    "FIREWORKS_AI": "fireworks_ai",
    "DEEPSEEK": "openai",
    "MISTRAL": "mistral",
    "CUSTOM": "custom",
}


class VisionLLMRouterService:
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
    def get_instance(cls) -> "VisionLLMRouterService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(
        cls,
        global_configs: list[dict],
        router_settings: dict | None = None,
    ) -> None:
        instance = cls.get_instance()

        if instance._initialized:
            logger.debug("Vision LLM Router already initialized, skipping")
            return

        model_list = []
        for config in global_configs:
            deployment = cls._config_to_deployment(config)
            if deployment:
                model_list.append(deployment)

        if not model_list:
            logger.warning(
                "No valid vision LLM configs found for router initialization"
            )
            return

        instance._model_list = model_list
        instance._router_settings = router_settings or {}

        default_settings = {
            "routing_strategy": "usage-based-routing",
            "num_retries": 3,
            "allowed_fails": 3,
            "cooldown_time": 60,
            "retry_after": 5,
        }

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
                "Vision LLM Router initialized with %d deployments, strategy: %s",
                len(model_list),
                final_settings.get("routing_strategy"),
            )
        except Exception as e:
            logger.error(f"Failed to initialize Vision LLM Router: {e}")
            instance._router = None

    @classmethod
    def _config_to_deployment(cls, config: dict) -> dict | None:
        try:
            if not config.get("model_name") or not config.get("api_key"):
                return None

            provider = config.get("provider", "").upper()
            if config.get("custom_provider"):
                provider_prefix = config["custom_provider"]
                model_string = f"{provider_prefix}/{config['model_name']}"
            else:
                provider_prefix = VISION_PROVIDER_MAP.get(provider, provider.lower())
                model_string = f"{provider_prefix}/{config['model_name']}"

            litellm_params: dict[str, Any] = {
                "model": model_string,
                "api_key": config.get("api_key"),
            }

            api_base = resolve_api_base(
                provider=provider,
                provider_prefix=provider_prefix,
                config_api_base=config.get("api_base"),
            )
            if api_base:
                litellm_params["api_base"] = api_base

            if config.get("api_version"):
                litellm_params["api_version"] = config["api_version"]

            if config.get("litellm_params"):
                litellm_params.update(config["litellm_params"])

            deployment: dict[str, Any] = {
                "model_name": "auto",
                "litellm_params": litellm_params,
            }

            if config.get("rpm"):
                deployment["rpm"] = config["rpm"]
            if config.get("tpm"):
                deployment["tpm"] = config["tpm"]

            return deployment

        except Exception as e:
            logger.warning(f"Failed to convert vision config to deployment: {e}")
            return None

    @classmethod
    def get_router(cls) -> Router | None:
        instance = cls.get_instance()
        return instance._router

    @classmethod
    def is_initialized(cls) -> bool:
        instance = cls.get_instance()
        return instance._initialized and instance._router is not None

    @classmethod
    def get_model_count(cls) -> int:
        instance = cls.get_instance()
        return len(instance._model_list)


def is_vision_auto_mode(config_id: int | None) -> bool:
    return config_id == VISION_AUTO_MODE_ID


def build_vision_model_string(
    provider: str, model_name: str, custom_provider: str | None
) -> str:
    if custom_provider:
        return f"{custom_provider}/{model_name}"
    prefix = VISION_PROVIDER_MAP.get(provider.upper(), provider.lower())
    return f"{prefix}/{model_name}"


def get_global_vision_llm_config(config_id: int) -> dict | None:
    from app.config import config

    if config_id == VISION_AUTO_MODE_ID:
        return {
            "id": VISION_AUTO_MODE_ID,
            "name": "Auto (Fastest)",
            "provider": "AUTO",
            "model_name": "auto",
            "is_auto_mode": True,
        }
    if config_id > 0:
        return None
    for cfg in config.GLOBAL_VISION_LLM_CONFIGS:
        if cfg.get("id") == config_id:
            return cfg
    return None
