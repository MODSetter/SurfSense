"""Regression tests for ``build_todos_mw``.

langchain's ``TodoListMiddleware.(a)wrap_model_call`` always appends a system
text block ``f"\\n\\n{self.system_prompt}"``. With an empty ``system_prompt``
that block is whitespace-only (``"\\n\\n"``), which Anthropic rejects:
``"system: text content blocks must contain non-whitespace text"``. The main
agent supplies its own todo guidance and wants the tool only, so an empty
prompt must NOT mutate the request's system message.
"""

from __future__ import annotations

import pytest
from langchain.agents.middleware import TodoListMiddleware

from app.agents.chat.multi_agent_chat.shared.middleware.todos import (
    _ToolOnlyTodoListMiddleware,
    build_todos_mw,
)

pytestmark = pytest.mark.unit


class _Request:
    def __init__(self) -> None:
        self.override_called = False

    def override(self, **_kwargs: object) -> _Request:
        self.override_called = True
        return self


@pytest.mark.parametrize("blank", ["", "   ", "\n\n"])
def test_blank_prompt_returns_tool_only_middleware(blank: str) -> None:
    mw = build_todos_mw(system_prompt=blank)
    assert isinstance(mw, _ToolOnlyTodoListMiddleware)
    # Still contributes the write_todos tool.
    assert any(getattr(t, "name", None) == "write_todos" for t in mw.tools)


async def test_tool_only_middleware_does_not_touch_system_message() -> None:
    mw = build_todos_mw(system_prompt="")
    request = _Request()
    captured: dict[str, object] = {}

    async def handler(req: _Request) -> str:
        captured["req"] = req
        return "ok"

    result = await mw.awrap_model_call(request, handler)

    assert result == "ok"
    assert captured["req"] is request
    assert request.override_called is False


def test_custom_prompt_uses_upstream_middleware() -> None:
    mw = build_todos_mw(system_prompt="custom todo guidance")
    assert isinstance(mw, TodoListMiddleware)
    assert not isinstance(mw, _ToolOnlyTodoListMiddleware)
    assert mw.system_prompt == "custom todo guidance"


def test_none_prompt_uses_upstream_default() -> None:
    mw = build_todos_mw()
    assert isinstance(mw, TodoListMiddleware)
    assert not isinstance(mw, _ToolOnlyTodoListMiddleware)
