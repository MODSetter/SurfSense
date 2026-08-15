"""Todo-list middleware (each consumer needs its own instance)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import TodoListMiddleware

from app.capabilities.core import ActivityDescriptor

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class _ToolOnlyTodoListMiddleware(TodoListMiddleware):  # type: ignore[type-arg]
    """``TodoListMiddleware`` that exposes the ``write_todos`` tool but appends
    no todo system prompt.

    Upstream ``TodoListMiddleware.(a)wrap_model_call`` *always* appends a system
    text block of ``f"\\n\\n{self.system_prompt}"``. With an empty
    ``system_prompt`` that block is whitespace-only (``"\\n\\n"``), which
    Anthropic rejects with ``"system: text content blocks must contain
    non-whitespace text"`` (OpenAI silently tolerates it). The main agent
    already documents todo usage in its own system prompt, so we skip the append
    entirely and let the request through unchanged.
    """

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return handler(request)

    async def awrap_model_call(
        self, request: Any, handler: Callable[[Any], Awaitable[Any]]
    ) -> Any:
        return await handler(request)


def build_todos_mw(*, system_prompt: str | None = None) -> TodoListMiddleware:
    """Build a todo-list middleware.

    - ``system_prompt=None``: use the upstream default todo system prompt.
    - ``system_prompt=""`` (or whitespace): contribute the ``write_todos`` tool
      without appending any todo system prompt. The main agent supplies its own
      todo guidance, and this avoids emitting a whitespace-only system block that
      Anthropic rejects.
    - otherwise: append the given custom todo system prompt.
    """
    if system_prompt is None:
        middleware = TodoListMiddleware()
    elif not system_prompt.strip():
        middleware = _ToolOnlyTodoListMiddleware()
    else:
        middleware = TodoListMiddleware(system_prompt=system_prompt)
    descriptor = ActivityDescriptor(
        active_title="Planning work",
        completed_title="Planned work",
        category="action",
        icon_key="list-todo",
        kind="write_todos",
        lifecycle="phase",
    ).as_metadata()
    for tool in middleware.tools:
        if tool.name == "write_todos":
            tool.metadata = {"activity_descriptor": descriptor}
    return middleware
