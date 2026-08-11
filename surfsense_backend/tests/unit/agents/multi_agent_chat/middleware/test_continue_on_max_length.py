"""Guard auto-continuation on output-token truncation.

A tool-call-free text answer cut off by ``max_tokens`` should be re-invoked and
stitched until it finishes; tool-call truncation and clean finishes pass through.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agents.chat.multi_agent_chat.main_agent.middleware.continue_on_max_length import (
    ContinueOnMaxLengthMiddleware,
)


@dataclass
class _FakeModel:
    max_tokens: int | None = 24


@dataclass
class _FakeRequest:
    model: _FakeModel
    messages: list[BaseMessage] = field(default_factory=list)

    def override(self, **overrides: Any) -> "_FakeRequest":
        return replace(self, **overrides)


@dataclass
class _FakeResponse:
    result: list[BaseMessage]
    structured_response: Any = None


def _ai(text: str, *, out: int, finish: str | None, tool_calls=None) -> AIMessage:
    return AIMessage(
        content=text,
        tool_calls=tool_calls or [],
        usage_metadata={"input_tokens": 5, "output_tokens": out, "total_tokens": 5 + out},
        response_metadata={"finish_reason": finish} if finish else {},
    )


def _handler_from(queue: list[AIMessage]):
    calls = {"n": 0}

    async def handler(_request):
        calls["n"] += 1
        return _FakeResponse(result=[queue.pop(0)])

    return handler, calls


def _text(resp: _FakeResponse) -> str:
    return resp.result[-1].content


@pytest.mark.asyncio
async def test_stitches_continuation_and_stops_when_complete():
    mw = ContinueOnMaxLengthMiddleware(max_continuations=3)
    handler, calls = _handler_from(
        [
            _ai("The ocean is ", out=24, finish="length"),
            _ai("vast and deep.", out=6, finish="stop"),
        ]
    )
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    resp = await mw.awrap_model_call(req, handler)

    assert _text(resp) == "The ocean is vast and deep."
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_clean_finish_passes_through_untouched():
    mw = ContinueOnMaxLengthMiddleware(max_continuations=3)
    handler, calls = _handler_from([_ai("All done.", out=5, finish="stop")])
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    resp = await mw.awrap_model_call(req, handler)

    assert _text(resp) == "All done."
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_truncated_tool_call_is_not_continued():
    mw = ContinueOnMaxLengthMiddleware(max_continuations=3)
    truncated_tool = _ai(
        "",
        out=24,
        finish="length",
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "t1"}],
    )
    handler, calls = _handler_from([truncated_tool])
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    resp = await mw.awrap_model_call(req, handler)

    assert resp.result[-1].tool_calls
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_respects_continuation_cap_when_model_keeps_truncating():
    mw = ContinueOnMaxLengthMiddleware(max_continuations=2)
    handler, calls = _handler_from(
        [_ai(c, out=24, finish="length") for c in "abcd"]
    )
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    resp = await mw.awrap_model_call(req, handler)

    assert calls["n"] == 3  # 1 initial + 2 continuations, then give up
    assert _text(resp) == "abc"


@pytest.mark.asyncio
async def test_successful_stitch_clears_truncation_marker():
    from app.services import token_tracking_service as tt

    acc = tt.start_turn()
    acc.truncated = True
    mw = ContinueOnMaxLengthMiddleware(max_continuations=3)
    handler, _ = _handler_from(
        [_ai("part ", out=24, finish="length"), _ai("whole.", out=6, finish="stop")]
    )
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    await mw.awrap_model_call(req, handler)

    assert acc.truncated is False


@pytest.mark.asyncio
async def test_cap_exhaustion_keeps_truncation_marker():
    from app.services import token_tracking_service as tt

    acc = tt.start_turn()
    acc.truncated = True
    mw = ContinueOnMaxLengthMiddleware(max_continuations=1)
    handler, _ = _handler_from(
        [_ai("a", out=24, finish="length"), _ai("b", out=24, finish="length")]
    )
    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])

    await mw.awrap_model_call(req, handler)

    assert acc.truncated is True


@pytest.mark.asyncio
async def test_continuation_context_includes_partial_and_nudge():
    mw = ContinueOnMaxLengthMiddleware(max_continuations=1)
    seen: dict[str, Any] = {}

    async def handler(request):
        seen["messages"] = list(request.messages)
        if len(seen["messages"]) > 1:
            return _FakeResponse(result=[_ai("END", out=3, finish="stop")])
        return _FakeResponse(result=[_ai("START ", out=24, finish="length")])

    req = _FakeRequest(model=_FakeModel(max_tokens=24), messages=[HumanMessage("hi")])
    resp = await mw.awrap_model_call(req, handler)

    assert _text(resp) == "START END"
    assert any(isinstance(m, AIMessage) and "START" in m.content for m in seen["messages"])
