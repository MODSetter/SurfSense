"""Todo-list middleware (each consumer needs its own instance)."""

from __future__ import annotations

from langchain.agents.middleware import TodoListMiddleware


def build_todos_mw(*, system_prompt: str | None = None) -> TodoListMiddleware:
    """Pass ``system_prompt=""`` to suppress the upstream prompt append. We use a custom system prompt in the main agent."""
    if system_prompt is None:
        return TodoListMiddleware()
    return TodoListMiddleware(system_prompt=system_prompt)
