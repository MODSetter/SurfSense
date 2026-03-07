"""
LiteLLM Router Service for Load Balancing

This module provides a singleton LiteLLM Router for automatic load balancing
across multiple LLM deployments. It handles:
- Rate limit management with automatic cooldowns
- Automatic failover and retries
- Usage-based routing to distribute load evenly

The router is initialized from global LLM configs and provides both
synchronous ChatLiteLLM-like interface and async methods.
"""

import logging
import re
import time
from typing import Any

import litellm
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.exceptions import ContextOverflowError
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from litellm import Router
from litellm.exceptions import (
    BadRequestError as LiteLLMBadRequestError,
    ContextWindowExceededError,
)

from app.utils.perf import get_perf_logger

litellm.json_logs = False
litellm.store_audit_logs = False

logger = logging.getLogger(__name__)

_CONTEXT_OVERFLOW_PATTERNS = re.compile(
    r"(input tokens exceed|context.{0,20}(length|window|limit)|"
    r"maximum context length|token.{0,20}(limit|exceed)|"
    r"too many tokens|reduce the length)",
    re.IGNORECASE,
)


def _is_context_overflow_error(exc: LiteLLMBadRequestError) -> bool:
    """Check if a BadRequestError is actually a context window overflow."""
    return bool(_CONTEXT_OVERFLOW_PATTERNS.search(str(exc)))


# Special ID for Auto mode - uses router for load balancing
AUTO_MODE_ID = 0

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
    "COMETAPI": "cometapi",
    "XAI": "xai",
    "BEDROCK": "bedrock",
    "AWS_BEDROCK": "bedrock",  # Legacy support
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
    "GITHUB_MODELS": "github",
    "HUGGINGFACE": "huggingface",
    "CUSTOM": "custom",
}


class LLMRouterService:
    """
    Singleton service for managing LiteLLM Router.

    The router provides automatic load balancing, failover, and rate limit
    handling across multiple LLM deployments.
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
    def get_instance(cls) -> "LLMRouterService":
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
        Initialize the router with global LLM configurations.

        Args:
            global_configs: List of global LLM config dictionaries from YAML
            router_settings: Optional router settings (routing_strategy, num_retries, etc.)
        """
        instance = cls.get_instance()

        if instance._initialized:
            logger.debug("LLM Router already initialized, skipping")
            return

        # Build model list from global configs
        model_list = []
        for config in global_configs:
            deployment = cls._config_to_deployment(config)
            if deployment:
                model_list.append(deployment)

        if not model_list:
            logger.warning("No valid LLM configs found for router initialization")
            return

        instance._model_list = model_list
        instance._router_settings = router_settings or {}

        # Default router settings optimized for rate limit handling
        default_settings = {
            "routing_strategy": "usage-based-routing",  # Best for rate limit management
            "num_retries": 3,
            "allowed_fails": 3,
            "cooldown_time": 60,  # Cooldown for 60 seconds after failures
            "retry_after": 5,  # Wait 5 seconds between retries
        }

        # Merge with provided settings
        final_settings = {**default_settings, **instance._router_settings}

        # Build a "auto-large" fallback group with deployments whose context
        # window exceeds the smallest deployment.  This lets the router
        # automatically fall back to a bigger-context model when gpt-4o (128K)
        # hits ContextWindowExceededError.
        full_model_list, ctx_fallbacks = cls._build_context_fallback_groups(model_list)

        try:
            router_kwargs: dict[str, Any] = {
                "model_list": full_model_list,
                "routing_strategy": final_settings.get(
                    "routing_strategy", "usage-based-routing"
                ),
                "num_retries": final_settings.get("num_retries", 3),
                "allowed_fails": final_settings.get("allowed_fails", 3),
                "cooldown_time": final_settings.get("cooldown_time", 60),
                "set_verbose": False,
            }
            if ctx_fallbacks:
                router_kwargs["context_window_fallbacks"] = ctx_fallbacks

            instance._router = Router(**router_kwargs)
            instance._initialized = True
            logger.info(
                "LLM Router initialized with %d deployments, "
                "strategy: %s, context_window_fallbacks: %s",
                len(model_list),
                final_settings.get("routing_strategy"),
                ctx_fallbacks or "none",
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM Router: {e}")
            instance._router = None

    @classmethod
    def _build_context_fallback_groups(
        cls, model_list: list[dict]
    ) -> tuple[list[dict], list[dict[str, list[str]]] | None]:
        """Create an ``auto-large`` model group for context-window fallbacks.

        Uses ``litellm.get_model_info`` to discover the context window of each
        deployment.  Deployments whose ``max_input_tokens`` exceeds the smallest
        window are duplicated into an ``auto-large`` group.  The returned
        fallback config tells the Router: on ``ContextWindowExceededError`` for
        ``auto``, retry with ``auto-large``.

        Returns:
            (full_model_list, context_window_fallbacks) — ``full_model_list``
            contains the original entries plus any ``auto-large`` duplicates.
            ``context_window_fallbacks`` is ``None`` when every deployment has
            the same context size (no useful fallback).
        """
        from litellm import get_model_info

        ctx_map: dict[str, int] = {}
        for dep in model_list:
            params = dep.get("litellm_params", {})
            base_model = params.get("base_model") or params.get("model", "")
            try:
                info = get_model_info(base_model)
                ctx = info.get("max_input_tokens")
                if isinstance(ctx, int) and ctx > 0:
                    ctx_map[base_model] = ctx
            except Exception:
                continue

        if not ctx_map:
            return model_list, None

        min_ctx = min(ctx_map.values())

        large_deployments: list[dict] = []
        for dep in model_list:
            params = dep.get("litellm_params", {})
            base_model = params.get("base_model") or params.get("model", "")
            if ctx_map.get(base_model, 0) > min_ctx:
                dup = {**dep, "model_name": "auto-large"}
                large_deployments.append(dup)

        if not large_deployments:
            return model_list, None

        logger.info(
            "Context-window fallback: %d large-context deployments "
            "(min_ctx=%d) added to 'auto-large' group",
            len(large_deployments),
            min_ctx,
        )
        return model_list + large_deployments, [{"auto": ["auto-large"]}]

    @classmethod
    def _config_to_deployment(cls, config: dict) -> dict | None:
        """
        Convert a global LLM config to a router deployment entry.

        Args:
            config: Global LLM config dictionary

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
                provider_prefix = PROVIDER_MAP.get(provider, provider.lower())
                model_string = f"{provider_prefix}/{config['model_name']}"

            # Build litellm params
            litellm_params = {
                "model": model_string,
                "api_key": config.get("api_key"),
            }

            # Add optional api_base
            if config.get("api_base"):
                litellm_params["api_base"] = config["api_base"]

            # Add any additional litellm parameters
            if config.get("litellm_params"):
                litellm_params.update(config["litellm_params"])

            # Extract rate limits if provided
            deployment = {
                "model_name": "auto",  # All configs use same alias for unified routing
                "litellm_params": litellm_params,
            }

            # Add rate limits from config if available
            if config.get("rpm"):
                deployment["rpm"] = config["rpm"]
            if config.get("tpm"):
                deployment["tpm"] = config["tpm"]

            return deployment

        except Exception as e:
            logger.warning(f"Failed to convert config to deployment: {e}")
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


_cached_context_profile: dict | None = None
_cached_context_profile_computed: bool = False

# Cached singleton instances keyed by (streaming,) to avoid re-creating on every call
_router_instance_cache: dict[bool, "ChatLiteLLMRouter"] = {}


def _get_cached_context_profile(router: Router) -> dict | None:
    """Compute and cache the min context profile across all router deployments.

    Called once on first ChatLiteLLMRouter creation; subsequent calls return
    the cached value. This avoids calling litellm.get_model_info() for every
    deployment on every request.
    """
    global _cached_context_profile, _cached_context_profile_computed
    if _cached_context_profile_computed:
        return _cached_context_profile

    from litellm import get_model_info

    min_ctx: int | None = None
    for deployment in router.model_list:
        params = deployment.get("litellm_params", {})
        base_model = params.get("base_model") or params.get("model", "")
        try:
            info = get_model_info(base_model)
            ctx = info.get("max_input_tokens")
            if isinstance(ctx, int) and ctx > 0 and (min_ctx is None or ctx < min_ctx):
                min_ctx = ctx
        except Exception:
            continue

    if min_ctx is not None:
        logger.info("ChatLiteLLMRouter profile: max_input_tokens=%d", min_ctx)
        _cached_context_profile = {"max_input_tokens": min_ctx}
    else:
        _cached_context_profile = None

    _cached_context_profile_computed = True
    return _cached_context_profile


class ChatLiteLLMRouter(BaseChatModel):
    """
    A LangChain-compatible chat model that uses LiteLLM Router for load balancing.

    This wraps the LiteLLM Router to provide the same interface as ChatLiteLLM,
    making it a drop-in replacement for auto-mode routing.

    Exposes a ``profile`` with ``max_input_tokens`` set to the smallest context
    window across all router deployments so that deepagents
    SummarizationMiddleware can use fraction-based triggers.

    **Singleton-ish**: Use ``get_auto_mode_llm()`` or call ``ChatLiteLLMRouter()``
    directly — instances without bound tools are cached per streaming flag to
    avoid per-request re-initialization overhead and memory growth.
    """

    # Use model_config for Pydantic v2 compatibility
    model_config = {"arbitrary_types_allowed": True}

    # Public attributes that Pydantic will manage
    model: str = "auto"
    streaming: bool = True

    # Bound tools and tool choice for tool calling
    _bound_tools: list[dict] | None = None
    _tool_choice: str | dict | None = None
    _router: Router | None = None

    def __init__(
        self,
        router: Router | None = None,
        bound_tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        **kwargs,
    ):
        try:
            super().__init__(**kwargs)
            resolved_router = router or LLMRouterService.get_router()
            object.__setattr__(self, "_router", resolved_router)
            object.__setattr__(self, "_bound_tools", bound_tools)
            object.__setattr__(self, "_tool_choice", tool_choice)
            if not self._router:
                raise ValueError(
                    "LLM Router not initialized. Call LLMRouterService.initialize() first."
                )

            computed_profile = _get_cached_context_profile(self._router)
            if computed_profile is not None:
                object.__setattr__(self, "profile", computed_profile)

            logger.debug(
                "ChatLiteLLMRouter ready (models=%d, streaming=%s, has_tools=%s)",
                LLMRouterService.get_model_count(),
                self.streaming,
                bound_tools is not None,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatLiteLLMRouter: {e}")
            raise

    @property
    def _llm_type(self) -> str:
        return "litellm-router"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "model_count": LLMRouterService.get_model_count(),
        }

    def bind_tools(
        self,
        tools: list[Any],
        *,
        tool_choice: str | dict | None = None,
        **kwargs: Any,
    ) -> "ChatLiteLLMRouter":
        """
        Bind tools to the model for function/tool calling.

        Args:
            tools: List of tools to bind (can be LangChain tools, Pydantic models, or dicts)
            tool_choice: Optional tool choice strategy ("auto", "required", "none", or specific tool)
            **kwargs: Additional arguments

        Returns:
            New ChatLiteLLMRouter instance with tools bound
        """
        from langchain_core.utils.function_calling import convert_to_openai_tool

        # Convert tools to OpenAI format
        formatted_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                # Already in dict format
                formatted_tools.append(tool)
            else:
                # Convert using LangChain utility
                try:
                    formatted_tools.append(convert_to_openai_tool(tool))
                except Exception as e:
                    logger.warning(f"Failed to convert tool {tool}: {e}")
                    continue

        # Create a new instance with tools bound
        return ChatLiteLLMRouter(
            router=self._router,
            bound_tools=formatted_tools if formatted_tools else None,
            tool_choice=tool_choice,
            model=self.model,
            streaming=self.streaming,
            **kwargs,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate a response using the router (synchronous).
        """
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = self._router.completion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                **call_kwargs,
            )
        except ContextWindowExceededError as e:
            perf.warning(
                "[llm_router] _generate CONTEXT_OVERFLOW msgs=%d in %.3fs",
                msg_count,
                time.perf_counter() - t0,
            )
            raise ContextOverflowError(str(e)) from e
        except LiteLLMBadRequestError as e:
            if _is_context_overflow_error(e):
                perf.warning(
                    "[llm_router] _generate CONTEXT_OVERFLOW msgs=%d in %.3fs",
                    msg_count,
                    time.perf_counter() - t0,
                )
                raise ContextOverflowError(str(e)) from e
            raise

        elapsed = time.perf_counter() - t0
        perf.info(
            "[llm_router] _generate completed msgs=%d tools=%d in %.3fs",
            msg_count,
            len(self._bound_tools) if self._bound_tools else 0,
            elapsed,
        )

        # Convert response to ChatResult with potential tool calls
        message = self._convert_response_to_message(response.choices[0].message)
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate a response using the router (asynchronous).
        """
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = await self._router.acompletion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                **call_kwargs,
            )
        except ContextWindowExceededError as e:
            perf.warning(
                "[llm_router] _agenerate CONTEXT_OVERFLOW msgs=%d in %.3fs",
                msg_count,
                time.perf_counter() - t0,
            )
            raise ContextOverflowError(str(e)) from e
        except LiteLLMBadRequestError as e:
            if _is_context_overflow_error(e):
                perf.warning(
                    "[llm_router] _agenerate CONTEXT_OVERFLOW msgs=%d in %.3fs",
                    msg_count,
                    time.perf_counter() - t0,
                )
                raise ContextOverflowError(str(e)) from e
            raise

        elapsed = time.perf_counter() - t0
        perf.info(
            "[llm_router] _agenerate completed msgs=%d tools=%d in %.3fs",
            msg_count,
            len(self._bound_tools) if self._bound_tools else 0,
            elapsed,
        )

        # Convert response to ChatResult with potential tool calls
        message = self._convert_response_to_message(response.choices[0].message)
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ):
        """
        Stream a response using the router (synchronous).
        """
        if not self._router:
            raise ValueError("Router not initialized")

        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = self._router.completion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                stream=True,
                **call_kwargs,
            )
        except ContextWindowExceededError as e:
            raise ContextOverflowError(str(e)) from e
        except LiteLLMBadRequestError as e:
            if _is_context_overflow_error(e):
                raise ContextOverflowError(str(e)) from e
            raise

        # Yield chunks
        for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                chunk_msg = self._convert_delta_to_chunk(delta)
                if chunk_msg:
                    yield ChatGenerationChunk(message=chunk_msg)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ):
        """
        Stream a response using the router (asynchronous).
        """
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = await self._router.acompletion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                stream=True,
                **call_kwargs,
            )
        except ContextWindowExceededError as e:
            perf.warning(
                "[llm_router] _astream CONTEXT_OVERFLOW msgs=%d in %.3fs",
                msg_count,
                time.perf_counter() - t0,
            )
            raise ContextOverflowError(str(e)) from e
        except LiteLLMBadRequestError as e:
            if _is_context_overflow_error(e):
                perf.warning(
                    "[llm_router] _astream CONTEXT_OVERFLOW msgs=%d in %.3fs",
                    msg_count,
                    time.perf_counter() - t0,
                )
                raise ContextOverflowError(str(e)) from e
            raise

        t_first_chunk = time.perf_counter()
        perf.info(
            "[llm_router] _astream connection established msgs=%d in %.3fs",
            msg_count,
            t_first_chunk - t0,
        )

        chunk_count = 0
        first_chunk_logged = False
        async for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                chunk_msg = self._convert_delta_to_chunk(delta)
                if chunk_msg:
                    chunk_count += 1
                    if not first_chunk_logged:
                        perf.info(
                            "[llm_router] _astream first chunk in %.3fs (total %.3fs from start)",
                            time.perf_counter() - t_first_chunk,
                            time.perf_counter() - t0,
                        )
                        first_chunk_logged = True
                    yield ChatGenerationChunk(message=chunk_msg)

        perf.info(
            "[llm_router] _astream completed chunks=%d total=%.3fs",
            chunk_count,
            time.perf_counter() - t0,
        )

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict]:
        """Convert LangChain messages to OpenAI format."""
        from langchain_core.messages import (
            AIMessage as AIMsg,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMsg):
                ai_msg: dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    ai_msg["content"] = msg.content
                # Handle tool calls
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    ai_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("args", "{}")
                                if isinstance(tc.get("args"), str)
                                else __import__("json").dumps(tc.get("args", {})),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(ai_msg)
            elif isinstance(msg, ToolMessage):
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content
                        if isinstance(msg.content, str)
                        else __import__("json").dumps(msg.content),
                    }
                )
            else:
                # Fallback for other message types
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                result.append({"role": role, "content": msg.content})

        return result

    def _convert_response_to_message(self, response_message: Any) -> AIMessage:
        """Convert a LiteLLM response message to a LangChain AIMessage."""
        import json

        content = getattr(response_message, "content", None) or ""

        # Check for tool calls
        tool_calls = []
        if hasattr(response_message, "tool_calls") and response_message.tool_calls:
            for tc in response_message.tool_calls:
                tool_call = {
                    "id": tc.id if hasattr(tc, "id") else "",
                    "name": tc.function.name if hasattr(tc, "function") else "",
                    "args": {},
                }
                # Parse arguments
                if hasattr(tc, "function") and hasattr(tc.function, "arguments"):
                    try:
                        tool_call["args"] = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_call["args"] = tc.function.arguments
                tool_calls.append(tool_call)

        if tool_calls:
            return AIMessage(content=content, tool_calls=tool_calls)
        return AIMessage(content=content)

    def _convert_delta_to_chunk(self, delta: Any) -> AIMessageChunk | None:
        """Convert a streaming delta to an AIMessageChunk."""

        content = getattr(delta, "content", None) or ""

        # Check for tool calls in delta
        tool_call_chunks = []
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tc in delta.tool_calls:
                chunk = {
                    "index": tc.index if hasattr(tc, "index") else 0,
                    "id": tc.id if hasattr(tc, "id") else None,
                    "name": tc.function.name
                    if hasattr(tc, "function") and hasattr(tc.function, "name")
                    else None,
                    "args": tc.function.arguments
                    if hasattr(tc, "function") and hasattr(tc.function, "arguments")
                    else "",
                }
                tool_call_chunks.append(chunk)

        if content or tool_call_chunks:
            if tool_call_chunks:
                return AIMessageChunk(
                    content=content, tool_call_chunks=tool_call_chunks
                )
            return AIMessageChunk(content=content)

        return None


def get_auto_mode_llm(
    *,
    streaming: bool = True,
) -> ChatLiteLLMRouter | None:
    """Return a cached ChatLiteLLMRouter for auto mode.

    Base (no tools) instances are cached per ``streaming`` flag so we
    avoid re-constructing them on every request.  ``bind_tools()`` still
    returns a fresh instance because bound tools differ per agent.
    """
    if not LLMRouterService.is_initialized():
        logger.warning("LLM Router not initialized for auto mode")
        return None

    cached = _router_instance_cache.get(streaming)
    if cached is not None:
        return cached

    try:
        instance = ChatLiteLLMRouter(streaming=streaming)
        _router_instance_cache[streaming] = instance
        return instance
    except Exception as e:
        logger.error(f"Failed to create ChatLiteLLMRouter: {e}")
        return None


def is_auto_mode(llm_config_id: int | None) -> bool:
    """
    Check if the given LLM config ID represents Auto mode.

    Args:
        llm_config_id: The LLM config ID to check

    Returns:
        True if this is Auto mode, False otherwise
    """
    return llm_config_id == AUTO_MODE_ID
