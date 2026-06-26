"""Todo-list middleware (each consumer needs its own instance)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import TodoListMiddleware

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
        return TodoListMiddleware()
    if not system_prompt.strip():
        return _ToolOnlyTodoListMiddleware()
    return TodoListMiddleware(system_prompt=system_prompt)
