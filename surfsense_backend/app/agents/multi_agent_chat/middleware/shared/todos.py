"""Todo-list middleware (each consumer needs its own instance)."""

from __future__ import annotations

from langchain.agents.middleware import TodoListMiddleware


def build_todos_mw() -> TodoListMiddleware:
    return TodoListMiddleware()
