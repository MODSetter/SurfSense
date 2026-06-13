import asyncio
import logging

import litellm
from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import Model, SearchSpace
from app.services.auto_model_pin_service import (
    auto_model_candidates,
    choose_auto_model_candidate,
)
from app.services.llm_router_service import (
    AUTO_MODE_ID,
    ChatLiteLLMRouter,
    is_auto_mode,
)
from app.services.model_capabilities import has_capability
from app.services.model_resolver import native_connection_from_config, to_litellm
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


def _legacy_config_connection(
    *,
    provider: str,
    model_name: str,
    api_key: str | None,
    api_base: str | None,
    custom_provider: str | None = None,
    litellm_params: dict | None = None,
    api_version: str | None = None,
) -> tuple[str, dict]:
    cfg = {
        "provider": provider.lower(),
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "custom_provider": custom_provider,
        "api_version": api_version,
        "litellm_params": litellm_params or {},
    }
    conn = native_connection_from_config(cfg)
    return to_litellm(conn, model_name)


class LLMRole:
    AGENT = "agent"  # For agent/chat operations


def get_global_llm_config(llm_config_id: int) -> dict | None:
    """
    Get a global LLM configuration by ID.
    Global configs have negative IDs. Auto mode (ID 0) is resolved through the
    model-candidate pipeline, not this legacy config lookup.

    Args:
        llm_config_id: The ID of the global config (must be negative)

    Returns:
        dict: Global config dictionary or None if not found
    """
    if llm_config_id >= 0:
        return None

    for cfg in config.GLOBAL_LLM_CONFIGS:
        if cfg.get("id") == llm_config_id:
            return cfg

    return None


def get_global_model(model_id: int) -> dict | None:
    return next((m for m in config.GLOBAL_MODELS if m.get("id") == model_id), None)


def get_global_connection(connection_id: int) -> dict | None:
    return next(
        (c for c in config.GLOBAL_CONNECTIONS if c.get("id") == connection_id),
        None,
    )


def _has_capability(model: dict | Model, capability: str) -> bool:
    return has_capability(model, capability)


def _chat_litellm_from_resolved(
    *,
    conn: dict | object,
    model_id: str,
    disable_streaming: bool = False,
) -> tuple[str, dict]:
    model_string, resolved_kwargs = to_litellm(conn, model_id)
    litellm_kwargs = {"model": model_string, **resolved_kwargs}
    if disable_streaming:
        litellm_kwargs["disable_streaming"] = True
    return model_string, litellm_kwargs


async def _get_db_model(
    session: AsyncSession,
    model_id: int,
    search_space: SearchSpace,
) -> Model | None:
    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .where(Model.id == model_id, Model.enabled.is_(True))
    )
    model = result.scalars().first()
    if not model or not model.connection or not model.connection.enabled:
        return None
    conn = model.connection
    if conn.search_space_id and conn.search_space_id != search_space.id:
        return None
    if conn.user_id and conn.user_id != search_space.user_id:
        return None
    return model


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
        model_string, resolved_kwargs = _legacy_config_connection(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
            custom_provider=custom_provider,
            litellm_params=litellm_params,
        )
        litellm_kwargs = {"model": model_string, **resolved_kwargs, "timeout": 30}

        from app.agents.chat.runtime.llm_config import (
            SanitizedChatLiteLLM,
        )

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
        role: LLM role ('agent')

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

        # Get the appropriate model binding ID based on role
        if role == LLMRole.AGENT:
            llm_config_id = search_space.chat_model_id
        else:
            logger.error(f"Invalid LLM role: {role}")
            return None

        if llm_config_id is None:
            logger.error(f"No {role} LLM configured for search space {search_space_id}")
            return None

        # Auto mode resolves to one concrete global or BYOK model from the
        # unified model-connections catalog.
        if is_auto_mode(llm_config_id):
            candidates = await auto_model_candidates(
                session,
                search_space_id=search_space_id,
                user_id=search_space.user_id,
                capability="chat",
            )
            if not candidates:
                logger.error("No chat-capable models available for Auto mode")
                return None
            llm_config_id = int(
                choose_auto_model_candidate(candidates, search_space_id)["id"]
            )

        # Check if this is a global virtual model (negative ID)
        if llm_config_id < 0:
            global_model = get_global_model(llm_config_id)
            if not global_model or not _has_capability(global_model, "chat"):
                logger.error(f"Global chat model {llm_config_id} not found")
                return None
            global_connection = get_global_connection(global_model["connection_id"])
            if not global_connection:
                logger.error(
                    "Global connection %s not found for model %s",
                    global_model["connection_id"],
                    llm_config_id,
                )
                return None

            _, litellm_kwargs = _chat_litellm_from_resolved(
                conn=global_connection,
                model_id=global_model["model_id"],
                disable_streaming=disable_streaming,
            )

            from app.agents.chat.runtime.llm_config import (
                SanitizedChatLiteLLM,
            )

            return SanitizedChatLiteLLM(**litellm_kwargs)

        model = await _get_db_model(session, llm_config_id, search_space)
        if not model or not _has_capability(model, "chat"):
            logger.error(
                f"Chat model {llm_config_id} not found in search space {search_space_id}"
            )
            return None

        _, litellm_kwargs = _chat_litellm_from_resolved(
            conn=model.connection,
            model_id=model.model_id,
            disable_streaming=disable_streaming,
        )

        from app.agents.chat.runtime.llm_config import (
            SanitizedChatLiteLLM,
        )

        return SanitizedChatLiteLLM(**litellm_kwargs)

    except Exception as e:
        logger.error(
            f"Error getting LLM instance for search space {search_space_id}, role {role}: {e!s}"
        )
        return None


async def get_agent_llm(
    session: AsyncSession, search_space_id: int, disable_streaming: bool = False
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's chat model instance."""
    return await get_search_space_llm_instance(
        session,
        search_space_id,
        LLMRole.AGENT,
        disable_streaming=disable_streaming,
    )


async def get_vision_llm(
    session: AsyncSession, search_space_id: int
) -> ChatLiteLLM | ChatLiteLLMRouter | None:
    """Get the search space's vision LLM instance for screenshot analysis.

    Resolves from the new connection/model role bindings:
    - Auto mode (ID 0): unified global/BYOK model candidate selection
    - Global (negative ID): virtual GLOBAL models from YAML
    - DB (positive ID): Model + Connection tables

    Premium global configs are wrapped in :class:`QuotaCheckedVisionLLM`
    so each ``ainvoke`` debits the search-space owner's premium credit
    pool. User-owned BYOK configs and free global configs are returned
    unwrapped — they don't consume premium credit (issue M).
    """
    from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM

    try:
        result = await session.execute(
            select(SearchSpace).where(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()
        if not search_space:
            logger.error(f"Search space {search_space_id} not found")
            return None

        owner_user_id = search_space.user_id

        # Prefer the selected chat model when it is vision-capable.
        chat_model_id = search_space.chat_model_id
        if chat_model_id and chat_model_id != AUTO_MODE_ID:
            if chat_model_id < 0:
                chat_model = get_global_model(chat_model_id)
                if chat_model and _has_capability(chat_model, "vision"):
                    global_connection = get_global_connection(
                        chat_model["connection_id"]
                    )
                    if global_connection:
                        model_string, litellm_kwargs = _chat_litellm_from_resolved(
                            conn=global_connection,
                            model_id=chat_model["model_id"],
                        )
                        from app.agents.chat.runtime.llm_config import (
                            SanitizedChatLiteLLM,
                        )

                        return SanitizedChatLiteLLM(**litellm_kwargs)
            else:
                chat_model = await _get_db_model(session, chat_model_id, search_space)
                if chat_model and _has_capability(chat_model, "vision"):
                    _, litellm_kwargs = _chat_litellm_from_resolved(
                        conn=chat_model.connection,
                        model_id=chat_model.model_id,
                    )
                    from app.agents.chat.runtime.llm_config import (
                        SanitizedChatLiteLLM,
                    )

                    return SanitizedChatLiteLLM(**litellm_kwargs)

        config_id = search_space.vision_model_id
        if config_id is None:
            logger.error(f"No vision LLM configured for search space {search_space_id}")
            return None

        if config_id == AUTO_MODE_ID:
            candidates = await auto_model_candidates(
                session,
                search_space_id=search_space_id,
                user_id=owner_user_id,
                capability="vision",
            )
            if not candidates:
                logger.error("No vision-capable models available for Auto mode")
                return None
            config_id = int(
                choose_auto_model_candidate(candidates, search_space_id)["id"]
            )

        if config_id < 0:
            global_model = get_global_model(config_id)
            if not global_model or not _has_capability(global_model, "vision"):
                logger.error(f"Global vision model {config_id} not found")
                return None

            global_connection = get_global_connection(global_model["connection_id"])
            if not global_connection:
                logger.error(
                    "Global connection %s not found for model %s",
                    global_model["connection_id"],
                    config_id,
                )
                return None

            model_string, litellm_kwargs = _chat_litellm_from_resolved(
                conn=global_connection,
                model_id=global_model["model_id"],
            )

            from app.agents.chat.runtime.llm_config import (
                SanitizedChatLiteLLM,
            )

            inner_llm = SanitizedChatLiteLLM(**litellm_kwargs)

            billing_tier = str(global_model.get("billing_tier", "free")).lower()
            if billing_tier == "premium":
                return QuotaCheckedVisionLLM(
                    inner_llm,
                    user_id=owner_user_id,
                    search_space_id=search_space_id,
                    billing_tier=billing_tier,
                    base_model=model_string,
                    quota_reserve_tokens=global_model.get("catalog", {}).get(
                        "quota_reserve_tokens"
                    ),
                )
            return inner_llm

        model = await _get_db_model(session, config_id, search_space)
        if not model or not _has_capability(model, "vision"):
            logger.error(
                f"Vision model {config_id} not found in search space {search_space_id}"
            )
            return None

        _, litellm_kwargs = _chat_litellm_from_resolved(
            conn=model.connection,
            model_id=model.model_id,
        )

        from app.agents.chat.runtime.llm_config import (
            SanitizedChatLiteLLM,
        )

        return SanitizedChatLiteLLM(**litellm_kwargs)

    except Exception as e:
        logger.error(
            f"Error getting vision LLM for search space {search_space_id}: {e!s}"
        )
        return None


def get_planner_llm() -> ChatLiteLLM | None:
    """Return a planner LLM instance from the first global config marked
    ``is_planner: true``, or ``None`` if no planner config is defined.

    The planner role handles short, structured internal tasks (KB search
    planning: query rewriting, date extraction, recency classification).
    These tasks are well-served by small/fast models (e.g. gpt-4o-mini,
    Claude Haiku, Azure gpt-5.x-nano) — using the user's chat LLM for them
    is unnecessarily expensive and slow.

    This helper reads from ``config.GLOBAL_LLM_CONFIGS`` (loaded at import
    time from ``global_llm_config.yaml``) so it has no DB cost and can be
    called synchronously from middleware/factory code. It returns the same
    instance shape as the global path of ``get_search_space_llm_instance``.

    Callers MUST fall back to their chat LLM when this returns ``None`` so
    deployments without a planner config keep working unchanged.
    """
    from app.agents.chat.runtime.llm_config import (
        create_chat_litellm_from_config,
    )

    planner_cfg = next(
        (cfg for cfg in config.GLOBAL_LLM_CONFIGS if cfg.get("is_planner") is True),
        None,
    )
    if not planner_cfg:
        return None
    return create_chat_litellm_from_config(planner_cfg)
