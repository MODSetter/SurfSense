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

import contextlib
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
from pydantic import Field

from app.services.context_admission import (
    compute_tool_tokens,
    trim_messages_to_fit_context,
)
from app.services.model_resolver import native_connection_from_config, to_litellm
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


_UNIVERSAL_CONTENT_TYPES = {
    "text",
    "image_url",
    "input_audio",
    "refusal",
    "audio",
    "file",
}


def _sanitize_content(content: Any) -> Any:
    """Normalise a LangChain message ``content`` field so it is safe for any
    downstream provider (Azure, OpenAI, OpenRouter, etc.).

    * Strips provider-specific block types (e.g. ``thinking`` from reasoning models).
    * Removes text blocks with blank text (Bedrock rejects ``{"type":"text","text":""}``)
    * Converts bare strings inside a list to ``{"type": "text", "text": ...}`` objects
      (Azure rejects raw strings in a content array).
    * Collapses a single-text-block list to a plain string for maximum compatibility.
    """
    if not isinstance(content, list):
        return content

    filtered: list[dict] = []
    for block in content:
        if isinstance(block, str):
            if block:
                filtered.append({"type": "text", "text": block})
        elif isinstance(block, dict):
            block_type = block.get("type", "text")
            if block_type not in _UNIVERSAL_CONTENT_TYPES:
                continue
            # Drop blank text blocks. Anthropic rejects whitespace-only system
            # blocks ("text content blocks must contain non-whitespace text"),
            # so treat whitespace-only as empty rather than only "".
            if block_type == "text" and not str(block.get("text") or "").strip():
                continue
            filtered.append(block)

    if not filtered:
        return ""
    if len(filtered) == 1 and filtered[0].get("type") == "text":
        return filtered[0].get("text", "")
    return filtered


# Special ID for Auto mode - uses router for load balancing
AUTO_MODE_ID = 0


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
    _premium_model_strings: set[str] = set()

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

        Configs with ``router_pool_eligible=False`` are skipped so that
        dynamic OpenRouter entries stay out of the shared router pool used
        by title-gen / sub-agent ``model="auto"`` flows. Those dynamic
        entries are still available for user-facing Auto-mode thread pinning
        via ``auto_model_pin_service``.

        Args:
            global_configs: List of global LLM config dictionaries from YAML
            router_settings: Optional router settings (routing_strategy, num_retries, etc.)
        """
        instance = cls.get_instance()

        if instance._initialized:
            logger.debug("LLM Router already initialized, skipping")
            return

        model_list = []
        premium_models: set[str] = set()
        for config in global_configs:
            if config.get("router_pool_eligible") is False:
                continue
            deployment = cls._config_to_deployment(config)
            if deployment:
                model_list.append(deployment)
                if config.get("billing_tier") == "premium":
                    params = deployment["litellm_params"]
                    model_string = params["model"]
                    premium_models.add(model_string)
                    base = params.get("base_model") or config.get("model_name", "")
                    if base and base != model_string:
                        premium_models.add(base)

        if not model_list:
            logger.warning("No valid LLM configs found for router initialization")
            return

        instance._model_list = model_list
        instance._premium_model_strings = premium_models
        instance._router_settings = router_settings or {}
        logger.info(
            "Router pool: %d deployments, premium model strings: %s",
            len(model_list),
            sorted(premium_models),
        )

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

        # Build a general-purpose fallback list so NotFound/timeout/rate-limit
        # style failures on one deployment don't bubble up as hard errors —
        # the router retries with a sibling deployment in ``auto-large``.
        # ``auto-large`` is the large-context subset of ``auto``; if it is
        # empty we fall back to ``auto`` itself so the router at least picks a
        # different deployment in the same group.
        fallbacks: list[dict[str, list[str]]] | None = None
        if ctx_fallbacks:
            fallbacks = [{"auto": ["auto-large"]}]

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
            if fallbacks:
                router_kwargs["fallbacks"] = fallbacks

            instance._router = Router(**router_kwargs)
            instance._initialized = True

            global _cached_context_profile, _cached_context_profile_computed
            _cached_context_profile = None
            _cached_context_profile_computed = False
            _router_instance_cache.clear()

            logger.info(
                "LLM Router initialized with %d deployments, "
                "strategy: %s, context_window_fallbacks: %s, fallbacks: %s",
                len(model_list),
                final_settings.get("routing_strategy"),
                ctx_fallbacks or "none",
                fallbacks or "none",
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM Router: {e}")
            instance._router = None

    @classmethod
    def rebuild(
        cls,
        global_configs: list[dict],
        router_settings: dict | None = None,
    ) -> None:
        """Reset the router and re-run ``initialize`` with fresh configs.

        ``initialize`` short-circuits once it has run to avoid re-creating the
        LiteLLM Router on every request; ``rebuild`` deliberately clears
        ``_initialized`` so a caller (e.g. background OpenRouter refresh)
        can force the pool to be rebuilt after catalogue changes.
        """
        instance = cls.get_instance()
        instance._initialized = False
        instance._router = None
        instance._model_list = []
        instance._premium_model_strings = set()
        cls.initialize(global_configs, router_settings)

    @classmethod
    def is_premium_model(cls, model_string: str) -> bool:
        """Return True if *model_string* belongs to a premium-tier deployment
        in the LiteLLM router pool.

        Scope: only covers configs with ``router_pool_eligible`` truthy. That
        includes static YAML premium configs AND dynamic OpenRouter *premium*
        entries (which opt in at generation time). Dynamic OpenRouter *free*
        entries are deliberately kept out of the router pool — OpenRouter
        enforces free-tier limits globally per account, so per-deployment
        router accounting can't represent them correctly — and therefore
        return ``False`` here, which matches their ``billing_tier="free"``
        (no premium quota).

        For per-request premium checks on an arbitrary config (static or
        dynamic, pool or non-pool), read ``agent_config.is_premium`` instead;
        that reflects the per-config ``billing_tier`` directly and is what
        user-facing Auto-mode thread pinning uses to bill correctly.
        """
        instance = cls.get_instance()
        return model_string in instance._premium_model_strings

    @classmethod
    def compute_premium_tokens(cls, calls: list) -> int:
        """Sum ``total_tokens`` for calls whose model is premium."""
        instance = cls.get_instance()
        total = sum(
            c.total_tokens for c in calls if c.model in instance._premium_model_strings
        )
        if calls:
            call_models = [c.model for c in calls]
            logger.info(
                "[premium_tokens] call models=%s, premium_set=%s, result=%d",
                call_models,
                sorted(instance._premium_model_strings),
                total,
            )
        return total

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

            model_string, resolved_kwargs = to_litellm(
                native_connection_from_config(config),
                config["model_name"],
            )
            litellm_params = {"model": model_string, **resolved_kwargs}

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
    """Compute and cache context profile across all router deployments.

    Called once on first ChatLiteLLMRouter creation; subsequent calls return
    the cached value. This avoids calling litellm.get_model_info() for every
    deployment on every request.

    Caches both ``max_input_tokens`` (minimum across deployments, used by
    SummarizationMiddleware) and ``max_input_tokens_upper`` (maximum across
    deployments, used for context-trimming so we can target the largest
    available model — the router's fallback logic handles smaller ones).
    """
    global _cached_context_profile, _cached_context_profile_computed
    if _cached_context_profile_computed:
        return _cached_context_profile

    from litellm import get_model_info

    min_ctx: int | None = None
    max_ctx: int | None = None
    token_count_model: str | None = None
    ctx_pairs: list[tuple[int, str]] = []
    for deployment in router.model_list:
        params = deployment.get("litellm_params", {})
        base_model = params.get("base_model") or params.get("model", "")
        try:
            info = get_model_info(base_model)
            ctx = info.get("max_input_tokens")
            if isinstance(ctx, int) and ctx > 0:
                if min_ctx is None or ctx < min_ctx:
                    min_ctx = ctx
                if max_ctx is None or ctx > max_ctx:
                    max_ctx = ctx
                if token_count_model is None:
                    token_count_model = base_model
                ctx_pairs.append((ctx, base_model))
        except Exception:
            continue

    if min_ctx is not None:
        token_count_models: list[str] = []
        if token_count_model:
            token_count_models.append(token_count_model)
        if ctx_pairs:
            ctx_pairs.sort(key=lambda x: x[0])
            smallest_model = ctx_pairs[0][1]
            largest_model = ctx_pairs[-1][1]
            if smallest_model not in token_count_models:
                token_count_models.append(smallest_model)
            if largest_model not in token_count_models:
                token_count_models.append(largest_model)
        logger.info(
            "ChatLiteLLMRouter profile: max_input_tokens=%d, upper=%s, token_models=%s",
            min_ctx,
            max_ctx,
            token_count_models,
        )
        _cached_context_profile = {
            "max_input_tokens": min_ctx,
            "max_input_tokens_upper": max_ctx,
            "token_count_model": token_count_model,
            "token_count_models": token_count_models,
        }
    else:
        _cached_context_profile = None

    _cached_context_profile_computed = True
    return _cached_context_profile


def _record_router_gen_ai(span: Any, *, model: str, usage: Any, started_at: float) -> None:
    """Emit gen_ai duration + token usage for a completed router call.

    Chokepoint instrumentation: covers every LLM caller that isn't wrapped by
    the agent's ``OtelSpanMiddleware`` (title-gen, vision, memory, podcast, ...).
    """
    from app.observability.domains import agent as _obs_agent

    _obs_agent.record_model_call_duration(
        (time.perf_counter() - started_at) * 1000, model=model, provider=None
    )
    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None
    _obs_agent.record_model_token_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        provider=None,
    )
    with contextlib.suppress(Exception):
        if span is not None:
            span.set_attribute("gen_ai.response.model", str(model))


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
    # Static kwargs that flow through to ``litellm.completion(...)`` on every
    # invocation (e.g. ``cache_control_injection_points`` set by
    # ``apply_litellm_prompt_caching``). Per-call ``**kwargs`` from
    # ``invoke()`` still take precedence — see ``_generate``/``_astream``.
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

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

    # -----------------------------------------------------------------
    # Context-aware trimming helpers
    # -----------------------------------------------------------------

    def _get_token_count_model_names(self) -> list[str]:
        """Return concrete model names usable by ``litellm.token_counter``.

        The router uses ``"auto"`` as the model group name but tokenizers need
        concrete model identifiers. We keep multiple candidates and take the
        most conservative count across them.
        """
        names: list[str] = []
        profile = getattr(self, "profile", None)
        if isinstance(profile, dict):
            tcms = profile.get("token_count_models")
            if isinstance(tcms, list):
                for name in tcms:
                    if isinstance(name, str) and name and name not in names:
                        names.append(name)
            tcm = profile.get("token_count_model")
            if isinstance(tcm, str) and tcm and tcm not in names:
                names.append(tcm)

        if self._router and self._router.model_list:
            for dep in self._router.model_list:
                params = dep.get("litellm_params", {})
                base = params.get("base_model") or params.get("model", "")
                if base and base not in names:
                    names.append(base)
                    if len(names) >= 3:
                        break
        if not names:
            return ["gpt-4o"]
        return names

    def _count_tokens(self, messages: list[dict]) -> int | None:
        """Return conservative token count across candidate deployment models."""
        from litellm import token_counter as _tc

        models = self._get_token_count_model_names()
        counts: list[int] = []
        for model_name in models:
            try:
                counts.append(_tc(messages=messages, model=model_name))
            except Exception:
                continue
        return max(counts) if counts else None

    def _get_max_input_tokens(self) -> int:
        """Return the max input tokens to use for context trimming.

        Prefers the *largest* context window across all deployments so we
        maximise usable context (the router's ``context_window_fallbacks``
        handle routing to the right model).  Falls back to the minimum
        profile value or a conservative default.
        """
        profile = getattr(self, "profile", None)
        if isinstance(profile, dict):
            upper = profile.get("max_input_tokens_upper")
            if isinstance(upper, int) and upper > 0:
                return upper
            lower = profile.get("max_input_tokens")
            if isinstance(lower, int) and lower > 0:
                return lower
        return 128_000

    def _trim_messages_to_fit_context(
        self,
        messages: list[dict],
        output_reserve_fraction: float = 0.10,
    ) -> list[dict]:
        """Trim message content via binary search to fit the model's context window.

        When the total token count exceeds the model's ``max_input_tokens``,
        this method identifies the largest messages (typically tool responses
        containing search results) and uses binary search on each to find the
        maximum content length that keeps the total within budget.

        Cutting prefers ``</document>`` XML boundaries so complete documents
        are preserved when possible.

        This is model-aware: it reads the context limit from
        ``litellm.get_model_info`` (cached in ``self.profile``) and counts
        tokens with ``litellm.token_counter``.
        """
        max_input = self._get_max_input_tokens()
        trimmed, final_tokens, budget = trim_messages_to_fit_context(
            messages,
            count_tokens=self._count_tokens,
            max_input_tokens=max_input,
            output_reserve_fraction=output_reserve_fraction,
            reserved_tokens=compute_tool_tokens(
                getattr(self, "_bound_tools", None), self._count_tokens
            ),
            estimate_on_count_failure=False,
        )
        if trimmed is not messages:
            get_perf_logger().info(
                "[llm_router] messages trimmed to %d tokens (budget=%d, max_input=%d)",
                final_tokens,
                budget,
                max_input,
            )
        return trimmed

    # -----------------------------------------------------------------

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

        # Create a new instance with tools bound. Carry through ``model_kwargs``
        # so static settings (e.g. cache_control_injection_points) survive the
        # bind_tools rebuild.
        return ChatLiteLLMRouter(
            router=self._router,
            bound_tools=formatted_tools if formatted_tools else None,
            tool_choice=tool_choice,
            model=self.model,
            streaming=self.streaming,
            model_kwargs=dict(self.model_kwargs),
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
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
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
        message = self._convert_response_to_message(
            response.choices[0].message, response=response
        )
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
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        # Chokepoint gen_ai span for callers without the agent middleware; when
        # the middleware already opened one, defer to it (no double-counting).
        from app.observability.domains import agent as _obs_agent

        _instrument = not _obs_agent.model_call_active()
        _span_cm = (
            _obs_agent.model_call_span(model_id=self.model)
            if _instrument
            else contextlib.nullcontext()
        )
        with _span_cm as _sp:
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
            message = self._convert_response_to_message(
                response.choices[0].message, response=response
            )
            if _instrument:
                _record_router_gen_ai(
                    _sp,
                    model=getattr(response, "model", None) or self.model,
                    usage=getattr(response, "usage", None),
                    started_at=t0,
                )
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
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
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
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        # Chokepoint gen_ai span for callers without the agent middleware; when
        # the middleware already opened one, defer to it (no double-counting).
        from app.observability.domains import agent as _obs_agent

        _instrument = not _obs_agent.model_call_active()
        _span_cm = (
            _obs_agent.model_call_span(model_id=self.model)
            if _instrument
            else contextlib.nullcontext()
        )
        with _span_cm as _sp:
            try:
                response = await self._router.acompletion(
                    model=self.model,
                    messages=formatted_messages,
                    stop=stop,
                    stream=True,
                    stream_options={"include_usage": True},
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
            # ``include_usage`` sends a trailing choices-less chunk carrying usage.
            usage = None
            model_name = self.model
            async for chunk in response:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                if chunk_model := getattr(chunk, "model", None):
                    model_name = chunk_model
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
            if _instrument:
                _record_router_gen_ai(
                    _sp, model=model_name, usage=usage, started_at=t0
                )

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict]:
        """Convert LangChain messages to OpenAI format."""
        from app.services.context_admission import convert_langchain_messages

        return convert_langchain_messages(messages, _sanitize_content)

    def _convert_response_to_message(
        self, response_message: Any, response: Any = None
    ) -> AIMessage:
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

        extra_kwargs: dict[str, Any] = {}
        if response:
            usage = getattr(response, "usage", None)
            if usage:
                extra_kwargs["usage_metadata"] = {
                    "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                }
            extra_kwargs["response_metadata"] = {
                "model_name": getattr(response, "model", "unknown"),
            }

        if tool_calls:
            return AIMessage(content=content, tool_calls=tool_calls, **extra_kwargs)
        return AIMessage(content=content, **extra_kwargs)

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
