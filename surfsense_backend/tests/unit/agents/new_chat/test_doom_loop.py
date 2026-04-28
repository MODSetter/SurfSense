"""Tests for DoomLoopMiddleware signature equality detection."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.agents.new_chat.middleware.doom_loop import DoomLoopMiddleware, _signature

pytestmark = pytest.mark.unit


def test_signature_is_stable_for_identical_args() -> None:
    a = _signature("search", {"q": "hello", "n": 10})
    b = _signature("search", {"n": 10, "q": "hello"})
    assert a == b


def test_signature_changes_with_args() -> None:
    a = _signature("search", {"q": "hello"})
    b = _signature("search", {"q": "world"})
    assert a != b


def test_signature_changes_with_name() -> None:
    a = _signature("search", {"q": "x"})
    b = _signature("read", {"q": "x"})
    assert a != b


class _FakeRuntime:
    def __init__(self, thread_id: str | None = "thread-1") -> None:
        self.config = {"configurable": {"thread_id": thread_id}}


def _msg_calling(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id}],
    )


def test_threshold_triggers_after_n_identical_calls() -> None:
    mw = DoomLoopMiddleware(threshold=3)
    runtime = _FakeRuntime()

    # First two calls — under threshold
    for i in range(2):
        out = mw.after_model(
            {"messages": [_msg_calling("repeat", {"x": 1}, f"call-{i}")]},
            runtime,
        )
        assert out is None

    # Third identical call should trigger ``langgraph.types.interrupt``.
    # In a unit-test context (no runnable graph), ``interrupt`` raises
    # ``RuntimeError`` because ``get_config`` has nothing to bind to —
    # we accept that as proof the interrupt path was taken (the
    # alternative would be no exception, which would mean the loop
    # detection never fired).
    with pytest.raises(Exception) as excinfo:
        mw.after_model(
            {"messages": [_msg_calling("repeat", {"x": 1}, "call-3")]},
            runtime,
        )
    name = type(excinfo.value).__name__.lower()
    assert (
        "interrupt" in name
        or "runtimeerror" in name
    ), f"Expected an interrupt-style exception, got {name}"


def test_does_not_trigger_when_args_differ() -> None:
    mw = DoomLoopMiddleware(threshold=2)
    runtime = _FakeRuntime()
    out = mw.after_model(
        {"messages": [_msg_calling("repeat", {"x": 1}, "1")]}, runtime
    )
    assert out is None
    out = mw.after_model(
        {"messages": [_msg_calling("repeat", {"x": 2}, "2")]}, runtime
    )
    assert out is None


def test_separate_threads_have_independent_windows() -> None:
    mw = DoomLoopMiddleware(threshold=2)
    rt_a = _FakeRuntime(thread_id="A")
    rt_b = _FakeRuntime(thread_id="B")

    mw.after_model({"messages": [_msg_calling("foo", {}, "1")]}, rt_a)
    # thread B should NOT count thread A's call
    out = mw.after_model({"messages": [_msg_calling("foo", {}, "1")]}, rt_b)
    assert out is None  # not yet at threshold for B


def test_invalid_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        DoomLoopMiddleware(threshold=1)
