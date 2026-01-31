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
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from litellm import Router

logger = logging.getLogger(__name__)

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

        try:
            instance._router = Router(
                model_list=model_list,
                routing_strategy=final_settings.get(
                    "routing_strategy", "usage-based-routing"
                ),
                num_retries=final_settings.get("num_retries", 3),
                allowed_fails=final_settings.get("allowed_fails", 3),
                cooldown_time=final_settings.get("cooldown_time", 60),
                set_verbose=False,  # Disable verbose logging in production
            )
            instance._initialized = True
            logger.info(
                f"LLM Router initialized with {len(model_list)} deployments, "
                f"strategy: {final_settings.get('routing_strategy')}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM Router: {e}")
            instance._router = None

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


class ChatLiteLLMRouter(BaseChatModel):
    """
    A LangChain-compatible chat model that uses LiteLLM Router for load balancing.

    This wraps the LiteLLM Router to provide the same interface as ChatLiteLLM,
    making it a drop-in replacement for auto-mode routing.
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
        """
        Initialize the ChatLiteLLMRouter.

        Args:
            router: LiteLLM Router instance. If None, uses the global singleton.
            bound_tools: Pre-bound tools for tool calling
            tool_choice: Tool choice configuration
        """
        try:
            super().__init__(**kwargs)
            # Store router and tools as private attributes
            resolved_router = router or LLMRouterService.get_router()
            object.__setattr__(self, "_router", resolved_router)
            object.__setattr__(self, "_bound_tools", bound_tools)
            object.__setattr__(self, "_tool_choice", tool_choice)
            if not self._router:
                raise ValueError(
                    "LLM Router not initialized. Call LLMRouterService.initialize() first."
                )
            logger.info(
                f"ChatLiteLLMRouter initialized with {LLMRouterService.get_model_count()} models"
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

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        # Call router completion
        response = self._router.completion(
            model=self.model,
            messages=formatted_messages,
            stop=stop,
            **call_kwargs,
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

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        # Call router async completion
        response = await self._router.acompletion(
            model=self.model,
            messages=formatted_messages,
            stop=stop,
            **call_kwargs,
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

        # Call router completion with streaming
        response = self._router.completion(
            model=self.model,
            messages=formatted_messages,
            stop=stop,
            stream=True,
            **call_kwargs,
        )

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

        formatted_messages = self._convert_messages(messages)

        # Add tools if bound
        call_kwargs = {**kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        # Call router async completion with streaming
        response = await self._router.acompletion(
            model=self.model,
            messages=formatted_messages,
            stop=stop,
            stream=True,
            **call_kwargs,
        )

        # Yield chunks asynchronously
        async for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                chunk_msg = self._convert_delta_to_chunk(delta)
                if chunk_msg:
                    yield ChatGenerationChunk(message=chunk_msg)

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


def get_auto_mode_llm() -> ChatLiteLLMRouter | None:
    """
    Get a ChatLiteLLMRouter instance for auto mode.

    Returns:
        ChatLiteLLMRouter instance or None if router not initialized
    """
    if not LLMRouterService.is_initialized():
        logger.warning("LLM Router not initialized for auto mode")
        return None

    try:
        return ChatLiteLLMRouter()
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
