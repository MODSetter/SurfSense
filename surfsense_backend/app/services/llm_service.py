import asyncio
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
    get_auto_mode_llm,
    is_auto_mode,
)
from app.services.token_tracking_service import token_tracker

# Configure litellm to automatically drop unsupported parameters
litellm.drop_params = True

# Memory controls: prevent unbounded internal accumulation
litellm.telemetry = False
litellm.cache = None
litellm.failure_callback = []
litellm.input_callback = []

litellm.callbacks = [token_tracker]

logger = logging.getLogger(__name__)


# Providers that require an interactive OAuth / device-flow login before
# issuing any completion. LiteLLM implements these with blocking sync polling
# (requests + time.sleep), which would freeze the FastAPI event loop if
# invoked from validation. They are never usable from a headless backend,
# so we reject them at the edge.
_INTERACTIVE_AUTH_PROVIDERS: frozenset[str] = frozenset(
    {
        "github_copilot",
        "github-copilot",
        "githubcopilot",
        "copilot",
    }
)

# Hard upper bound for a single validation call. Must exceed the ChatLiteLLM
# request timeout (30s) by a small margin so a well-behaved provider never
# trips the watchdog, while any pathological/blocking provider is killed.
_VALIDATION_TIMEOUT_SECONDS: float = 35.0


def _is_interactive_auth_provider(
    provider: str | None, custom_provider: str | None
) -> bool:
    """Return True if the given provider triggers interactive OAuth in LiteLLM."""
    for raw in (custom_provider, provider):
        if not raw:
            continue
        normalized = raw.strip().lower().replace(" ", "_")
        if normalized in _INTERACTIVE_AUTH_PROVIDERS:
            return True
    return False


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
            "name": "Auto (Fastest)",
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
    # Reject providers that require interactive OAuth/device-flow auth.
    # LiteLLM's github_copilot provider (and similar) uses a blocking sync
    # Authenticator that polls GitHub for up to several minutes and prints a
    # device code to stdout. Running it on the FastAPI event loop will freeze
    # the entire backend, so we refuse them up front.
    if _is_interactive_auth_provider(provider, custom_provider):
        msg = (
            "Provider requires interactive OAuth/device-flow authentication "
            "(e.g. github_copilot) and cannot be used in a hosted backend. "
            "Please choose a provider that authenticates via API key."
        )
        logger.warning(
            "Rejected LLM config validation for interactive-auth provider "
            "(provider=%r, custom_provider=%r)",
            provider,
            custom_provider,
        )
        return False, msg

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
                "MINIMAX": "openai",
                "GITHUB_MODELS": "github",
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

        from app.agents.new_chat.llm_config import SanitizedChatLiteLLM

        llm = SanitizedChatLiteLLM(**litellm_kwargs)

        # Run the test call in a worker thread with a hard timeout. Some
        # LiteLLM providers have synchronous blocking code paths (e.g. OAuth
        # authenticators that call time.sleep and requests.post) that would
        # otherwise freeze the asyncio event loop. Offloading to a thread and
        # bounding the wait keeps the server responsive even if a provider
        # misbehaves.
        test_message = HumanMessage(content="Hello")
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(llm.invoke, [test_message]),
                timeout=_VALIDATION_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "LLM config validation timed out after %ss for model: %s",
                _VALIDATION_TIMEOUT_SECONDS,
                model_string,
            )
            return (
                False,
                f"Validation timed out after {int(_VALIDATION_TIMEOUT_SECONDS)}s. "
                "The provider is unreachable or requires interactive "
                "authentication that is not supported by the backend.",
            )

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
    session: AsyncSession,
    search_space_id: int,
    role: str,
    disable_streaming: bool = False,
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
                return get_auto_mode_llm(streaming=not disable_streaming)
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
                    "MINIMAX": "openai",
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

            if disable_streaming:
                litellm_kwargs["disable_streaming"] = True

            from app.agents.new_chat.llm_config import SanitizedChatLiteLLM

            return SanitizedChatLiteLLM(**litellm_kwargs)

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
                "MINIMAX": "openai",
                "GITHUB_MODELS": "github",
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

        if disable_streaming:
            litellm_kwargs["disable_streaming"] = True

        from app.agents.new_chat.llm_config import SanitizedChatLiteLLM

        return SanitizedChatLiteLLM(**litellm_kwargs)

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
    session: AsyncSession, search_space_id: int, disable_streaming: bool = False
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's document summary LLM instance."""
    return await get_search_space_llm_instance(
        session,
        search_space_id,
        LLMRole.DOCUMENT_SUMMARY,
        disable_streaming=disable_streaming,
    )


async def get_vision_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's vision LLM instance for screenshot analysis.

    Resolves from the dedicated VisionLLMConfig system:
    - Auto mode (ID 0): VisionLLMRouterService
    - Global (negative ID): YAML configs
    - DB (positive ID): VisionLLMConfig table

    Premium global configs are wrapped in :class:`QuotaCheckedVisionLLM`
    so each ``ainvoke`` debits the search-space owner's premium credit
    pool. User-owned BYOK configs and free global configs are returned
    unwrapped — they don't consume premium credit (issue M).
    """
    from app.db import VisionLLMConfig
    from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM
    from app.services.vision_llm_router_service import (
        VISION_PROVIDER_MAP,
        VisionLLMRouterService,
        get_global_vision_llm_config,
        is_vision_auto_mode,
    )

    try:
        result = await session.execute(
            select(SearchSpace).where(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()
        if not search_space:
            logger.error(f"Search space {search_space_id} not found")
            return None

        config_id = search_space.vision_llm_config_id
        if config_id is None:
            logger.error(f"No vision LLM configured for search space {search_space_id}")
            return None

        owner_user_id = search_space.user_id

        if is_vision_auto_mode(config_id):
            if not VisionLLMRouterService.is_initialized():
                logger.error(
                    "Vision Auto mode requested but Vision LLM Router not initialized"
                )
                return None
            try:
                # Auto mode is currently treated as free at the wrapper
                # level — the underlying router can dispatch to either
                # premium or free YAML configs but routing decisions are
                # opaque. If/when we want to bill Auto-routed vision
                # calls we'd need to thread the resolved deployment's
                # billing_tier back from the router. For now we keep
                # parity with chat Auto, which also doesn't pre-classify.
                return ChatLiteLLMRouter(
                    router=VisionLLMRouterService.get_router(),
                    streaming=True,
                )
            except Exception as e:
                logger.error(f"Failed to create vision ChatLiteLLMRouter: {e}")
                return None

        if config_id < 0:
            global_cfg = get_global_vision_llm_config(config_id)
            if not global_cfg:
                logger.error(f"Global vision LLM config {config_id} not found")
                return None

            if global_cfg.get("custom_provider"):
                model_string = (
                    f"{global_cfg['custom_provider']}/{global_cfg['model_name']}"
                )
            else:
                prefix = VISION_PROVIDER_MAP.get(
                    global_cfg["provider"].upper(),
                    global_cfg["provider"].lower(),
                )
                model_string = f"{prefix}/{global_cfg['model_name']}"

            litellm_kwargs = {
                "model": model_string,
                "api_key": global_cfg["api_key"],
            }
            if global_cfg.get("api_base"):
                litellm_kwargs["api_base"] = global_cfg["api_base"]
            if global_cfg.get("litellm_params"):
                litellm_kwargs.update(global_cfg["litellm_params"])

            from app.agents.new_chat.llm_config import SanitizedChatLiteLLM

            inner_llm = SanitizedChatLiteLLM(**litellm_kwargs)

            billing_tier = str(global_cfg.get("billing_tier", "free")).lower()
            if billing_tier == "premium":
                return QuotaCheckedVisionLLM(
                    inner_llm,
                    user_id=owner_user_id,
                    search_space_id=search_space_id,
                    billing_tier=billing_tier,
                    base_model=model_string,
                    quota_reserve_tokens=global_cfg.get("quota_reserve_tokens"),
                )
            return inner_llm

        # User-owned (positive ID) BYOK configs — always free.
        result = await session.execute(
            select(VisionLLMConfig).where(
                VisionLLMConfig.id == config_id,
                VisionLLMConfig.search_space_id == search_space_id,
            )
        )
        vision_cfg = result.scalars().first()
        if not vision_cfg:
            logger.error(
                f"Vision LLM config {config_id} not found in search space {search_space_id}"
            )
            return None

        if vision_cfg.custom_provider:
            model_string = f"{vision_cfg.custom_provider}/{vision_cfg.model_name}"
        else:
            prefix = VISION_PROVIDER_MAP.get(
                vision_cfg.provider.value.upper(),
                vision_cfg.provider.value.lower(),
            )
            model_string = f"{prefix}/{vision_cfg.model_name}"

        litellm_kwargs = {
            "model": model_string,
            "api_key": vision_cfg.api_key,
        }
        if vision_cfg.api_base:
            litellm_kwargs["api_base"] = vision_cfg.api_base
        if vision_cfg.litellm_params:
            litellm_kwargs.update(vision_cfg.litellm_params)

        from app.agents.new_chat.llm_config import SanitizedChatLiteLLM

        return SanitizedChatLiteLLM(**litellm_kwargs)

    except Exception as e:
        logger.error(
            f"Error getting vision LLM for search space {search_space_id}: {e!s}"
        )
        return None


# Backward-compatible alias (LLM preferences are now per-search-space, not per-user)
async def get_user_long_context_llm(
    session: AsyncSession,
    user_id: str,
    search_space_id: int,
    disable_streaming: bool = False,
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """
    Deprecated: Use get_document_summary_llm instead.
    The user_id parameter is ignored as LLM preferences are now per-search-space.
    """
    return await get_document_summary_llm(
        session, search_space_id, disable_streaming=disable_streaming
    )
