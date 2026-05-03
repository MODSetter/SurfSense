"""Reference plugin: substitute ``{{year}}`` in tool descriptions.

Demonstrates the :meth:`AgentMiddleware.awrap_tool_call` hook -- the
plugin sees every tool invocation and can rewrite the request *or* the
result. This particular plugin is read-only and only transforms the
*description* the user might see in error messages (no request
mutation).

The plugin is built as a factory function so the entry-point loader can
inject :class:`PluginContext` (containing the agent's LLM, search-space
ID, etc.). The factory signature
``Callable[[PluginContext], AgentMiddleware]`` is the only contract --
SurfSense doesn't define a custom plugin protocol on top of LangChain's
:class:`AgentMiddleware`.

Wire-up in ``pyproject.toml`` (illustrative; the in-repo plugin doesn't
need this -- it's already on the import path)::

    [project.entry-points."surfsense.plugins"]
    year_substituter = "app.agents.new_chat.plugins.year_substituter:make_middleware"
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware

if TYPE_CHECKING:  # pragma: no cover - type-only
    from langchain.agents.middleware.types import ToolCallRequest
    from langchain_core.messages import ToolMessage
    from langgraph.types import Command

    from app.agents.new_chat.plugin_loader import PluginContext


logger = logging.getLogger(__name__)


class _YearSubstituterMiddleware(AgentMiddleware):
    """Replace ``{{year}}`` in the result text with the current UTC year."""

    tools = ()

    def __init__(self, year: int | None = None) -> None:
        super().__init__()
        self._year = str(year if year is not None else datetime.now(UTC).year)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        result = await handler(request)
        try:
            from langchain_core.messages import ToolMessage

            if (
                isinstance(result, ToolMessage)
                and isinstance(result.content, str)
                and "{{year}}" in result.content
            ):
                new_text = result.content.replace("{{year}}", self._year)
                result = ToolMessage(
                    content=new_text,
                    tool_call_id=result.tool_call_id,
                    id=result.id,
                    name=result.name,
                    status=result.status,
                    artifact=result.artifact,
                )
        except Exception:  # pragma: no cover - defensive
            logger.exception("year_substituter plugin failed; passing original result")
        return result


def make_middleware(ctx: PluginContext) -> AgentMiddleware:
    """Plugin factory used by :func:`load_plugin_middlewares`."""
    # Plugin is intentionally small so it has no state to threading-protect
    # and ignores ``ctx`` beyond demonstrating that the loader passes it in.
    _ = ctx
    return _YearSubstituterMiddleware()


__all__ = ["make_middleware"]
