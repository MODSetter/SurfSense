"""
``_noop`` provider-compatibility tool + injection middleware.

OpenCode injects a ``_noop`` tool for LiteLLM/Bedrock/Copilot when the
model call has empty tools but message history includes prior
``tool_calls`` — some providers 400 in that shape (see
``opencode/packages/opencode/src/session/llm.ts:209-228``). SurfSense uses
LiteLLM, and the compaction summarize call (no tools, history full of
tool calls) hits this. Tier 1.5 in the OpenCode-port plan.

Operation: a :class:`NoopInjectionMiddleware` ``wrap_model_call`` checks
if the request has zero tools but the last AI message in history includes
``tool_calls``. If yes, it injects the ``_noop`` tool only — never globally,
mirroring opencode's gating exactly. The :func:`noop_tool` returns empty
content when called (which it should never be in practice).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

NOOP_TOOL_NAME = "_noop"
NOOP_TOOL_DESCRIPTION = (
    "Do not call this tool. It exists only for API compatibility."
)


@tool(name_or_callable=NOOP_TOOL_NAME, description=NOOP_TOOL_DESCRIPTION)
def noop_tool() -> str:
    """Return empty content. Never expected to be called."""
    return ""


# Provider markers that benefit from ``_noop`` injection. These match
# opencode's gating list. We also accept any string containing one of
# these substrings (so e.g. ``litellm`` matches ``ChatLiteLLM``).
_NOOP_NEEDED_PROVIDERS: tuple[str, ...] = (
    "litellm",
    "bedrock",
    "copilot",
)


def _provider_needs_noop(model: Any) -> bool:
    """Heuristic: does this model's provider need the _noop injection?"""
    try:
        ls_params = model._get_ls_params()
        provider = str(ls_params.get("ls_provider", "")).lower()
    except Exception:
        provider = ""

    if not provider:
        cls_name = type(model).__name__.lower()
        provider = cls_name

    return any(needle in provider for needle in _NOOP_NEEDED_PROVIDERS)


def _last_ai_has_tool_calls(messages: list[Any]) -> bool:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return bool(msg.tool_calls)
    return False


class NoopInjectionMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Inject the ``_noop`` tool only when the provider would otherwise 400.

    The check fires per model call, not at agent build time, because the
    summarization path generates a no-tool subcall at runtime. The
    extra tool is appended to ``request.tools`` as an instance — the
    actual ``langchain_core.tools.BaseTool`` is bound on every call site
    that creates the agent.
    """

    def __init__(self, *, noop_tool_instance: Any | None = None) -> None:
        super().__init__()
        self._noop_tool = noop_tool_instance or noop_tool
        self.tools = []

    def _should_inject(self, request: ModelRequest[ContextT]) -> bool:
        if request.tools:
            return False
        if not _last_ai_has_tool_calls(request.messages):
            return False
        return _provider_needs_noop(request.model)

    def _augmented(self, request: ModelRequest[ContextT]) -> ModelRequest[ContextT]:
        return request.override(tools=[self._noop_tool])

    def wrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> Any:
        if self._should_inject(request):
            logger.debug("Injecting _noop tool for provider compatibility")
            return handler(self._augmented(request))
        return handler(request)

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> Any:
        if self._should_inject(request):
            logger.debug("Injecting _noop tool for provider compatibility")
            return await handler(self._augmented(request))
        return await handler(request)


__all__ = [
    "NOOP_TOOL_DESCRIPTION",
    "NOOP_TOOL_NAME",
    "NoopInjectionMiddleware",
    "_provider_needs_noop",
    "noop_tool",
]
